#!/usr/bin/env /router/bin/python-2.7.4
###############################################################################
# This script is used to for pulling a workspace and run the SDK regression
# scripts. It will send email with the results.
#
# Copyright (c) 2015 by Cisco Systems, Inc.
# All rights reserved.
###############################################################################
from __future__ import print_function
import os
import datetime
import subprocess
import shutil
import sys
from optparse import OptionParser
from collections import *
import smtplib
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

wireless_regression_exe = "/ws/siche-sjc/macallan/wireless_regression.py"

def workspace_name(storage):
    '''
    Get the various derived names from the workspace.
    '''
    now = datetime.date.today()
    view_tag = "SDKREG_%s" % (now.strftime('%m%d%Y'))
    workspace = "%s/%s" % (storage, view_tag)
    binos_root = "%s/binos" % (workspace)
    ios_root = "%s/ios" % (workspace)
    sdk_root = "%s/platforms/ngwc/doppler_sdk" % (binos_root)
    return (view_tag, workspace, binos_root, ios_root, sdk_root)

def workspace_version(workspace):
    '''
    Get the workspace version by looking at the SCM information.
    '''
    os.chdir(workspace)
    if os.path.exists(".workspace"):
        os.remove(".workspace")
    cmd = "acme desc -workspace -short > .workspace"
    try:
        output = subprocess.check_call(cmd, stderr=subprocess.STDOUT, shell=True)
        print(output)
    except subprocess.CalledProcessError:
        print("#### acme command to get workspace info failed")

    workspace = "none"
    devline = "none"
    devline_ver = "none"
    for line in open(".workspace"):
        if "Workspace" in line:
            workspace = line.split(":")[1] 
            workspace = workspace.strip() 
        if "Devline  " in line:
            devline = line.split(":")[1]
            devline = devline.strip()
        if "Devline Ver " in line:
            devline_ver = line.split(":")[1]
            devline_ver = devline_ver.strip()

    return (workspace, devline, devline_ver)


def get_dvpp_release(asic):
    '''
    Get the DVPP release information.
    '''
    dvpp_rel = {
        "CS" : "dopplercs_cima_S0101_R2014_07_27",
        "D" : "dopplerd_T0097_2_R2015_07_01",
        "G" : "dopplerg_S0639_R2014_10_22",
        "GStub" : "dopplerg_S0639_R2014_10_22",
        "E" : "dopplere_S1295_R2015_10_06_P4"
    }

    return dvpp_rel[asic]

def get_current_label(workspace):
    '''
    Get the current label from the workspace. 
    '''
    os.chdir(workspace)
    tmp_file = '%s/tmp_file' % (workspace)
    cmd = "acme desc -comp .acme_project -short > %s" % (tmp_file)
    try:
        output = subprocess.check_call(cmd, stderr=subprocess.STDOUT, shell=True)
        print(output)
    except subprocess.CalledProcessError:
        print("#### acme command to get workspace info failed")
        return "none"

    label_file_p = open(tmp_file, "r")
    current_label = label_file_p.readline()
    label_file_p.close()
    os.remove(tmp_file)
    return current_label.split("@")[1].rstrip()

def get_current_label_from_file(location, filename):
    '''
    Get the current label from the file from the regression directory.
    '''
    label = ''
    os.chdir(location)
    label_file = '%s/%s' % (location, filename)
    try: 
        with  open(label_file, "r") as label_file_p:
            label = label_file_p.readline()
    except EnvironmentError:
        print("open file %s failed" % label_file)
    return label.rstrip()

def update_current_label(workspace, filename, label):
    label_file = '%s/%s' % (workspace, filename)
    if os.path.exists(label_file):
        os.remove(label_file)
    label_file_p = open(label_file, "w")
    label_file_p.write(label.rstrip())
    label_file_p.close()

def get_bugs_info(workspace, current_label, last_label):
    '''
    Get the DDTSs fixed between the current label and last label.
    '''
    bugs_info = ''
    tmp_file = "%s/tmp_file" % (workspace)
    cmd = 'acme refpoint_list -start_ver %s -end_ver %s -comp .acme_project > %s' % \
              (last_label, current_label, tmp_file)
    try:
        output = subprocess.check_call(cmd, stderr=subprocess.STDOUT, shell=True)
        print(output)
    except subprocess.CalledProcessError:
        print("#### acme command to get workspace info failed")
        return "none"

    for line in open(tmp_file):
        if "Change ID:" in line:
            bugs_info += line.split(':')[1].rstrip() + '  by '
        if "Created By:" in line:
            bugs_info += line.split(':')[1].rstrip() + '\n'
            
    os.remove(tmp_file)

    print("Current label: %s Latest Label: %s" % (current_label, last_label))
    print(bugs_info)
    return bugs_info


def send_email(email, subject, body):
    '''
    Construction an email message and send it to the email
    address provided. This function will get the workspace
    information and other information to construct the
    email.
    '''
    outer = MIMEMultipart()
    outer['To'] = email
    outer['From'] = os.environ['USER'] + "@cisco.com"
    outer['Subject'] = subject 

    outer.attach(MIMEText(body, "plain"))
    composed = outer.as_string()
    smtp_inst = smtplib.SMTP('localhost')
    smtp_inst.sendmail(email, email, composed)
    smtp_inst.quit()

def send_email_ws(email):
    '''
    The workspace build failed hence send email regarding this.
    '''
    send_email(email, "REGRESSION: worspace pull failed", "")

def send_email_binos_root(email, binos_root, bugs):
    '''
    Send email regarding the binos root failure.
    '''
    body = "DDTSs fixed since last successful run:\n\n"
    for line in open(bugs): 
        body += line

    workspace, devline, devline_ver = workspace_version(binos_root)
    body += "\n\nSDK Workspace: %s (%s/%s)\n\n\n" % (workspace, devline, devline_ver)
    send_email(email, "REGRESSION: x86_64 binos root build failed", body)

def send_email_asic_build(email, binos_root, asic, bugs, new_code):
    '''
    Send email regarding the ASIC build failure.
    '''
    body = "DDTSs fixed since last successful run:\n\n"
    for line in open(bugs): 
        body += line

    workspace, devline, devline_ver = workspace_version(binos_root)
    body += "\n\nSDK Workspace: %s (%s/%s)\n\n\n" % (workspace, devline, devline_ver)
    if new_code:
        send_email(email, "REGRESSION: Doppler%s (new AFD/CAD) build failed" % (asic), body)
    else:
        send_email(email, "REGRESSION: Doppler%s build failed" % (asic), body)

def patch_ws (workspace = '.'):
    os.chdir(workspace)
    cmds = ('patch -p1 -f < /ws/siche-sjc/macallan/WiredToWirelessBridging_CS.stanley.diff',
            'patch -p1 -f < /ws/siche-sjc/macallan/wireless_spectra.diff',
            'patch -p1 -f < /ws/siche-sjc/macallan/spectra_scripts.diff')
    
    for cmd in cmds:
        try:
            subprocess.call(cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            print("Error: ", e)

def parse_test_runner_output (output):
    if "Results" not in output:
        return ''
    results = {}
    for l in output.split('\n'):
        if '|' in l:
            results[l.split('|')[1].strip()] = l.split('|')[2].strip()

    return results

def send_email_regression_results (email, output):
    body = ''
    output['CS'] = parse_test_runner_output('Results' + output['CS'].split('Results')[1])
    output['D'] = parse_test_runner_output('Results' + output['D'].split('Results')[1])
    cs=sum(1 for res in output['CS'].values() if res == 'PASSED')
    d=sum(1 for res in output['D'].values() if res == 'PASSED')
    body += """
    Summary:
    DopplerCS: {cs}/{total}
    DopplerD: {d}/{total}\n""".format(cs = cs, d = d, total = len(output['CS'].keys()))
    testcases = output[output.keys()[0]].keys()
    tbl_format = '| {:<35} | {:<25} | {:<25} |'
    body += tbl_format.format('Testname', 'DopplerCS', 'DopplerD')+'\n'
    body += '\n'.join([tbl_format.format(t, output['CS'][t], output['D'][t]) for t in testcases])

    body += """
    All tests were run with new code, feature mode.
    """
    send_email(email, "Wireless Regression Multi-Doppler Results", body)    

def run_regression(storage, branch, email):
    '''
    This routine will create the workspace from latest and build the
    binos linkfarm and spectra targets. Then it will launch the regression
    of the software against a standard DVPP release for that ASIC. The
    results will be sent to the alias or email provide.
    '''
    # Create workspace in storage area and pull the workspace
    view_tag, workspace, binos_root, ios_root, sdk_root = workspace_name(storage)
    if os.path.exists(workspace):
        print('Workspace %s already exists' % (workspace))
        shutil.rmtree(workspace)
        print('Workspace %s removed' % (workspace))

    os.makedirs(workspace)
    os.chdir(workspace)

    # Set path for the BINOS build, 
    # Since it is a cronjob the path needs to be passed 
    cur_path = os.environ['PATH']
    paths = [
             '/auto/step-build/cobalt/mcp_cable',
             '/auto/binos-tools/bin',
             '/router/bin',
             '/usr/local/binr',
             '/usr/local/etc',
             '/binr',
             '/usr/X11R6/bin',
             '/usr/sbin',
             '/sbin',
             '/usr/bin',
             '/usr/cisco/bin'
             ]
    paths.append(cur_path)
    os_path = ':'.join(paths)
    os.environ['PATH'] = os_path
    os.environ['BINOS_ROOT'] = binos_root
    d_env = dict(os.environ)
    d_env['BINOS_ROOT'] = os.environ['BINOS_ROOT']
    d_env['PATH'] = os.environ['PATH']

    # Pull work space
    cmd = "acme nw -project %s -sb xe" % (branch)
    print("Executing (%s)" % (cmd))
    try:
        subprocess.check_call(
            cmd, stderr=subprocess.STDOUT, shell=True, env=d_env)
    except subprocess.CalledProcessError:
        print("###Error in pulling workspace")
        # Send email for build failure
        shutil.rmtree(workspace)
        send_email_ws(email)
        return False

    patch_ws(workspace)

    # Create the regression workspace logs directory
    log_dir = "%s/regression/%s" % (storage, view_tag)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Get the last label when the regression run was successful
    # If there are no such files then create one with the 
    # current label of xe workspace.
    label_dir = "%s/regression" % (storage)
    last_label = get_current_label_from_file(label_dir, "last_label")
    current_label = get_current_label(workspace)

    # Get all DDTSs fixed between the last and current workspace.
    bugs_info = get_bugs_info(workspace, current_label, last_label)
    bugs_file = "%s/bugs.%s" % (log_dir, view_tag)
    if os.path.exists(bugs_file):
        os.remove(bugs_file)
    bugs_file_p = open(bugs_file, "w")
    bugs_file_p.write(bugs_info)
    bugs_file_p.close()

    # Start the build for the x86_64_binos_root.
    # Once the binos_root is done build all ASIC builds
    cmd = "mcp_ios_precommit -- -j16 build_x86_64_binos_root"
    print("Executing (%s)" % (cmd))
    os.chdir("%s/sys" % (ios_root))
    try:
        subprocess.check_call(
            cmd, stderr=subprocess.STDOUT, shell=True, env=d_env)
    except subprocess.CalledProcessError:
        print("###Error in building binos linkfarm")
        # Send email for build failure
        send_email_binos_root(email, binos_root, bugs_file)
        shutil.rmtree(workspace)
        return False

    output = {}
    # Start the ASIC builds for the new AFD/CAD and execute the regressions
    for asic in ['CS', 'D']:
        cmd = "%s -b %s -a Doppler%s -e %s -k %s -n -p" % \
            (wireless_regression_exe, 
             binos_root, asic, 'siche@cisco.com', bugs_file)

        try:
            print("Executing (%s)" % (cmd))
            output[asic] = subprocess.check_output(
                cmd, stderr=subprocess.STDOUT, shell=True, env=d_env)
        except subprocess.CalledProcessError:
            print("###Error in executing regression for spectra Doppler%s (new AFD/RAL)" % (asic))
            send_email_asic_build(email, binos_root, asic, bugs_file, False)
            
        continue

    send_email_regression_results(email, output) 

    update_current_label(label_dir, "last_label", current_label)
    shutil.rmtree(workspace)
    return True

######################################################################
# Main entry point for the SDK regression script.
######################################################################
def main():
    '''
    This is the main routine which gets invoked when the script
    is invoked to run regression from the cron job.
    '''
    parser = OptionParser(usage="usage: %prog\n"
                          "-e <email address>\n"
                          "-s <storage>\n"
                          "-b <branch>\n",
                          description="SDK regression cron program")
    parser.add_option("-e", "--email", dest="email", help="Email Address")
    parser.add_option("-s", "--storage", dest="storage",
                      help="Starage for the worksapce")
    parser.add_option("-b", "--branch", dest="branch", help="Branch name")
    (options, args) = parser.parse_args()

    email = ''
    storage = ''
    branch = ''

    if options.email:
        email = options.email
    else:
        print('email not specified')
        sys.exit(1)

    branch = 'macallan_dev'
    if options.branch:
        branch = options.branch

    if options.storage:
        storage = options.storage
        if not os.path.exists(storage):
            print('Storage %s provided does not exist' % (storage))
            sys.exit(1)
    else:
        print('Storage location is not specified')
        sys.exit(1)

    print('Starting regression in %s in %s' % (branch, storage))
    print('Results will be sent to %s' % (email))
    result = run_regression(storage, branch, email)
    if not result:
        print('Workspace build failed')

if __name__ == '__main__':
    main()
