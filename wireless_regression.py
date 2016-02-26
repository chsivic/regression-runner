#!/usr/bin/env /router/bin/python-2.7.4
######################################################################
# Build script for PAQ libraries and executable from a nightly build
# label with the nightly build linkfarm. Once the nightly build is
# done it will perform multiple builds to achieve the following.
#
#  - Run all possible UT scripts in DopplerSDK. Then attach the test
#    results to the email report.
#  - Setup the code coverage tools and build the image again for
#    code coverage. It will analyze the coverage and send the summary
#    report.
#  - It will run the Valgrind memory analysis tool while executing
#    the UT test cases. It will attach the results of that to the
#    email.
#
# January 2014, Manas Pati
#
# Copyright (c) 2013-2015 by cisco Systems, Inc.
# All rights reserved.
######################################################################
from __future__ import print_function
import os
import sys
import platform
import shutil
from optparse import OptionParser
import smtplib
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pprint import pprint
import subprocess
import datetime
import time
import filecmp
from subprocess import check_output, Popen

regression_repo = "/auto/ecsg-paq1/sdk_regression/"
test_runner_exe = "/ws/siche-sjc/macallan/test_runner.py"

######################################################################
# UT Programs Specifies which programs needs to be executed and where
# the output will be located.
# The tupple consists of the following strings.
#    ( area, program, prefix, arguments, logfile, valgrind, nonDP)
######################################################################
def get_wireless_testcases ():
    implemented_testcases = []
    with open("/ws/siche-sjc/macallan/Wireless-Test-Plan.2016.csv") as f:
        for line in f:
            words = line.split(',')
            if words[3] != "MISSING":
                implemented_testcases.append(words[2])
    return implemented_testcases

##########################################################################
# Gstub does not have all functionalities hence we can not execute the
# regular test cases instead we need to use the Gstub specific test cases.
##########################################################################
UTPrograms_GStub = [
    ("CAPABILITY","capUT", "ignore", "cap_ut.log", True, True),
    ("Layer2", "L2GStubBasic",  "WAIT=2", "Layer2.log", False, False),
    ("Layer2IngressBasicStub", "L2IngressBasicStub",  "WAIT=2", "Layer2Ingress.log", False, False),
    ("Layer2EgressBasicStub", "L2EgressBasicStub",  "WAIT=2", "Layer2Egress.log", False, False),
    ("Layer3IngressBasicStub", "L3IngressBasicStub",  "WAIT=2", "Layer3Ingress.log", False, False),
    ("Layer3EgressBasicStub", "L3EgressBasicStub",  "WAIT=2", "Layer3Egress.log", False, False),
]

# FIXME DOPPLERE continuing investigating UT failures and add new UT cases.
UTPrograms_DopplerE = [
    ("CAPABILITY","capUT", "ignore", "cap_ut.log", True, True),
# Doppler E hasn't enabled all asic modules, these tests will fail
#    ("AAL",  "aalUT", "ignore", "aal_ut.log", True, True),
#    ("SPECTRA", "spectraUT", "ignore", "spectra_ut.log", True, True),
#    ("Layer2", "L2Basic",  "\"WAIT=1 CIMA_MON_OPTS=ALL OFFLOADS=0 PTLOG_LEVEL=DEBUG\"", "Layer2.log", False, False),
    ("Layer2", "L2Basic",  "WAIT=2", "Layer2.log", False, False),
    ("Layer2_feature", "L2Basic",  "\"WAIT=1 TESTMODE=FEATURE\"", "Layer2_feature.log", False, False),
#   Enabling stats related tests
    ("IngressAclStats", "PACLBasic",  "WAIT=1", "PACLBasic.log", False, False),
    ("EgressAclStats", "RACLEgressBasic",  "WAIT=1", "RACLEgressBasic.log", False, False),
    ("PortFwdStats", "L2BasicOffload",  "WAIT=1", "L2BasicOffload.log", False, False),
#   Enabling L2Multicast Tests
    ("Layer2IPV4Multicast", "L2mV4Forward",  "WAIT=1", "L2mV4Forward.log", False, False),
    ("Layer2IPV4Multicast_feature", "L2mV4Forward",  "\"WAIT=1 TESTMODE=FEATURE\"", "L2mV4Forward_feature.log", False, False),
    ("Layer2IPV6Multicast", "L2mV6Forward",  "WAIT=1", "L2mV6Forward.log", False, False),
    ("Layer2IPV6Multicast_feature", "L2mV6Forward",  "\"WAIT=1 TESTMODE=FEATURE\"", "L2mV6Forward_feature.log", False, False),
    ("Layer2IGMPQUERY", "L2mV4IgmpQuery",  "WAIT=1", "L2mV4IgmpQuery.log", False, False),

    ("IPv4", "L3Basic",  "WAIT=1", "IPv4.log", False, False),
    ("IPv4_feature", "L3Basic",  "\"WAIT=1 TESTMODE=FEATURE\"", "IPv4_feature.log", False, False),
    ("IPv6", "L3Ipv6RoutedPortToRoutedPort",  "WAIT=1", "IPv6.log", False, False),    
    ("IPv6_feature", "L3Ipv6RoutedPortToRoutedPort", "\"WAIT=1 TESTMODE=FEATURE\"", "IPv6_feature.log", False, False),   #   Enabling Qos Tests 
    ("QOS_Basic", "QosPlainV4",  "WAIT=1", "QosPlainV4.log", False, False),
    ("QosClassifyDscpIngressV4", "QosClassifyDscpIngressV4",  "WAIT=1", "QosClassifyDscpIngressV4.log", False, False),
    ("QosClassifyDscpEgressV4", "QosClassifyDscpEgressV4",  "WAIT=1", "QosClassifyDscpEgressV4.log", False, False),
    ("MacsecIngress", "MacsecIngress",  "WAIT=1", "MacsecIngressV4.log", False, False),
    ("MacsecEgress", "MacsecEgress",  "WAIT=1", "MacsecEgressV4.log", False, False),
    ("RACLBasic", "RACLBasic",  "WAIT=1", "RACLBasic.log", False, False),
    ("L3mV4Route", "L3mV4Route",  "WAIT=1", "L3mV4Route.log", False, False),
    ("L3mV6Route", "L3mV6Route",  "WAIT=1", "L3mV6Route.log", False, False),
]
######################################################################
# Asic version to name and vice versa
######################################################################
asicVerToName = {
    "351": "Doppler",
    "3c2": "DopplerCS",
    "3e1": "DopplerD",
    "3e0": "DopplerG",
    "3f1": "DopplerE"
}

asicNameToVer = {
    "Doppler"  : "351",
    "DopplerCS": "3c2",
    "DopplerD" : "3e1",
    "DopplerG" : "3e0",
    "DopplerE" : "3f1"
}

######################################################################
# Utility funtions to get the directories important for execution
######################################################################

def spectraDir(binos_root):
    return "%s/platforms/ngwc/doppler_sdk/spectra" % (binos_root)

def scriptsDir(binos_root):
    return "%s/scripts" % (spectraDir(binos_root))

def logDir(binos_root):
    return "%s/logs/" % (spectraDir(binos_root))

def resultDir(binos_root):
    return "%s/results/" % (spectraDir(binos_root))

######################################################################
# Clean the worksapce and build the tree again from scratch
######################################################################
def cleanWorkspace(env):
    binos_root, asic, new_code, no_attach, cflow = env

    os.chdir(binos_root)

    # First clean the workspace
    cleanCmd = "%s/platforms/ngwc/doppler_sdk/tools/scripts/spectra_build.py -a %s -c -o -q" % \
                            (binos_root, asic)
    if cflow:
        cleanCmd = "%s -f" % (cleanCmd)

    try:
        output = subprocess.check_call(cleanCmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError:
        print("#### Spectra clean failed")
        sys.exit(1)

    # If the new code is tested we have to get rid of the linkfarm and build it again
    # as all modules need to be built again.
    if new_code:
        cleanCmd = "%s -p" % (cleanCmd)
        try:
            output = subprocess.check_call(cleanCmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError:
            print("#### Spectra clean failed")

def cleanAndBuild(env, coverage):
    binos_root, asic, new_code, no_attach, cflow = env
    
    os.chdir(binos_root)

    cleanWorkspace(env)
    # Now build spectra
    buildCmd = "%s/platforms/ngwc/doppler_sdk/tools/scripts/spectra_build.py -a %s" % \
                            (binos_root, asic)
    if cflow:
        buildCmd = "%s -f" % (buildCmd)

    if new_code:
        buildCmd = "%s -p" % (buildCmd)

    try:
        output = subprocess.check_call(buildCmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError:
        print("#### Spectra build failed")
        sys.exit(1)


def updateWorkspace(binos_root):
    os.chdir(binos_root)
    os.chdir("..")
    os.environ['ACME_VERBOSITY'] = 'terse'
    cmd = "acme update -comp binos@macallan_dev/latest"
    try:
        output = subprocess.check_call(cmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError:
        print("Workspace update failed")
        sys.exit(1)

    os.chdir(binos_root)
    os.environ['ACME_VERBOSITY'] = 'normal'

    merge = ''
    conflicts = 0
    for line in open("%s/.ACMEROOT/log/update_log" % (binos_root)):
        if "Update operation type summary (count):" in line:
            merge = line.split(" ")[10]

    print("Merge conflicts: %s" % (merge) )
    if not merge:
        conflicts = int(merge.split(':')[1])

    return conflicts

def parse_test_runner_output (output):
    if "Results" not in output:
        return ''
    results = {}
    for l in output.split('\n'):
        if '|' in l:
            results[l.split('|')[1].strip()] = l.split('|')[2].strip()

    return results

def loop_utPrograms (binos_root, asic, utPrograms):
    utResults = {}
    # Run all programs in a loop and copy the logs to the results
    # directory. If the program failed to execute then the results
    # are stored in a to be returned to the caller.
    for utName, utTest, utArgs, utLogs, utValgrind, utNonDp in utPrograms:
        coreDump = False
        buildFailed = False
        runFailed = False
        output = ''

        # If there are any core files in the directory then remove it
        # before running the test.
        for filename in os.listdir(scriptsDir(binos_root)):
            path = os.path.join(scriptsDir(binos_root), filename)
            if not os.path.isfile(path):
                continue
            if "core" in filename.lower():
                os.remove(filename)

        utCmd = "%s -q -a %s -t %s" % \
                (test_runner_exe, asic, utTest) 
        if not utNonDp:
            utLogs = "%s.%s.%s" % (utLogs, asic, utArgs)
            utCmd = "%s -l %s" % (utCmd, utLogs)

        if "ignore" not in utArgs:
            utCmd = "%s -r %s" % (utCmd, utArgs)
        
        try:
            print("\nExecuting (%s)" % (utCmd))
            output = subprocess.check_output(utCmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError:
            print("#### UT test execution failed")
        else:
            print(output)
            test_runner_result = parse_test_runner_output(output)

        if not os.path.exists(logDir(binos_root) + utLogs):
            runFailed = True

        for filename in os.listdir(scriptsDir(binos_root)):
            path = os.path.join(scriptsDir(binos_root), filename)
            if not os.path.isfile(path):
                continue
            if "core" in filename.lower():
                print("Coredump observed for the %s" % (utName))
                coreDump = True

        utResults[utName] = (runFailed, coreDump, utValgrind,
                             test_runner_result[utName])

    return utResults


######################################################################
# run SDK UT code and collect the results.
######################################################################
def runTest(env, tool):
    binos_root, asic, new_code, no_attach, cflow = env
    valgrind, coverage = tool

    os.environ['INSTALL_DIR_PATH'] = binos_root
    os.environ['PTLOG_LEVEL'] = '3'

    os.chdir(binos_root)
    utResults = {}
    utPrograms = {}

    # If there are any core files in the directory then remove it
    # before running the test.
    for filename in os.listdir(scriptsDir(binos_root)):
        path = os.path.join(scriptsDir(binos_root), filename)
        if not os.path.isfile(path):
            continue
        if "core" in filename.lower():
            os.remove(path)

    # Remove the results directory and created it before each run
    if os.path.exists(resultDir(binos_root)):
        shutil.rmtree(resultDir(binos_root))
    os.makedirs(resultDir(binos_root))

#    utPrograms = [(t,t,"TESTMODE=FEATURE",t,'','') for t in get_wireless_testcases()]

#    utResults = loop_utPrograms(binos_root, asic, utPrograms)

    cmd = [test_runner_exe, '-p', '-a', asic,
        '-t', ':'.join(get_wireless_testcases()), '-r', '"TESTMODE=FEATURE"']
    print("\nExecuting(%s)" % ' '.join(cmd))
    try:
        output = ''
        p = Popen(cmd, stdout = subprocess.PIPE, bufsize=1, universal_newlines=True)
        with p.stdout:
            for line in iter(p.stdout.readline, b''):
                print(line, end='')
                output += line
        p.wait()
    except subprocess.CalledProcessError as e:
        print("#### test_runner error: %s" % e)
    else:
        test_runner_result = parse_test_runner_output(output)
    utResults = {t:(False, False, '', test_runner_result[t]) for t in test_runner_result.keys()}

    return utResults

######################################################################
# Email the results of the Tests which was run previously with the
# runTest().
######################################################################
def emailTestResults(env, tool, results, email, bugs, cdets, start_time):
    binos_root, asic, new_code, no_attach, cflow = env
    valgrind, coverage = tool

    # Construct a multipart MIME message. The sender email address is
    # the user running this tool.
    outer = MIMEMultipart()
    outer['To'] = email
    outer['From'] = os.environ['USER'] + "@cisco.com"
    cronJobText = ""

    # Based upon the type of tool we ran the email subject needs to be
    # constructed.
    subText = "Doppler SDK - %s" % (asic)
    if new_code:
        subText = " %s (New AFD/CAD)" % (subText)
    if cflow:
        subText = "%s (CFLOW)" % (subText)

    if valgrind:
        outer['Subject'] = "MEMORY ANALYSIS: %s" % (subText)
    else:
        outer['Subject'] = "REGRESSION: %s" % (subText)

    emailBodyText =  "Doppler SDK Regression Test Results\n"
    emailBodyText += "------ ----------------------------\n\n"

    emailBodyText += "Time spent: %s seconds\n" % (time.time() - start_time)

    if bugs and os.path.exists(bugs):
        emailBodyText += "Bugs fixed since last successful run:\n\n"
        for line in open(bugs):
            emailBodyText += line 
        emailBodyText += "\n\n" 

    
    # Get workspace information
    if os.path.exists(".workspace"):
        os.remove(".workspace")
    cmd = "acme desc -workspace -short > .workspace"
    try:
        output = subprocess.check_call(cmd, stderr=subprocess.STDOUT, shell=True)
    except subprocess.CalledProcessError:
        print("#### acme command to get workspace info failed")

    workspace = ""
    devline = ""
    devline_ver = ""
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

    emailBodyText += "\nSDK Workspace: %s (%s/%s)" % (workspace, devline, devline_ver)


    emailBodyText += "\nResult Directory: %s\n" % (resultDir(binos_root))
    tbl_format = '\n| {:<35} | {:<15} | {:<40} |'
    tblBorder = "\n+--------------------------------+--------------+------------------------------------------+"
    cronJobText += tblBorder 
    cronJobText += tbl_format.format("TestName" , "Result", "LogFile")
    cronJobText += tblBorder 

    for utName, utResult in sorted(results.items()):
        runFailed, coreDump, utValgrind, test_runner_result = utResult
        if coreDump:
            cronJobText += tbl_format.format(utName, "FAILED", "Crashed")
            continue
        if runFailed:
            cronJobText += tbl_format.format(utName, "FAILED", "RunFailed")
            continue

        cronJobText += tbl_format.format(utName, test_runner_result, '') 

        if valgrind and utValgrind:
            valgrindFile = resultDir(binos_root) + utName + "_Valgrind.txt"
            if not os.path.exists(valgrindFile):
                cronJobText += "\nValgrind Analysis Data: %s_Valgrind.txt \
                                  (ERROR: File Not found)\n" % (utName)
            else:
                cronJobText += "\nValgrind Analysis Data: %s_Valgrind.txt\n" % (utName)
                addText = False
                for line in open(valgrindFile):
                    cronJobText += line

    cronJobText += tblBorder 

    emailBodyText += cronJobText

    outer.attach(MIMEText(emailBodyText, "plain"))

    # FIXME DOPPLERE Not attaching results for E, remove when ready
    if (asic != "DopplerE") and not no_attach:
        for filename in os.listdir(resultDir(binos_root)):
            path = os.path.join(resultDir(binos_root), filename)
            if not os.path.isfile(path):
                continue
            ctype, encoding = mimetypes.guess_type(path)
            if ctype is None or encoding is not None:
                ctype = 'application/octect-stream'
            maintype, subtype = ctype.split('/', 1)
            if maintype == 'text':
                fp = open(path)
                msg = MIMEText(fp.read(), _subtype=subtype)
            else:
                continue

            msg.add_header('Content-Disposition', 'attachment', filename=filename)
            outer.attach(msg)

    composed = outer.as_string()
    s = smtplib.SMTP('localhost')
    s.sendmail(email, email, composed)
    s.quit()


######################################################################
# Main entry point of the regression suite.
######################################################################
def main():
    parser = OptionParser(usage="usage: %prog\n"
                          "-a <asic>\n"
                          "-b <binos_root>\n"
                          "-v <valgrind>\n"
                          "-l <Run with latest version>\n"
                          "-k <Bugs fixed.>\n"
                          "-e <email address>\n"
                          "-n <No attachment>\n"
                          "-p <new code>\n"
                          "-f <cflow>\n"
                          "-c <cdets>\n"
                          "-s <skip clean and build>\n"
                          "-r <skip clean after run>\n",
                          description="Nightly Build script")
    parser.add_option("-a", "--asic", dest="asic", help="ASIC type")
    parser.add_option("-b", "--binos_root", dest="binosroot",
                      help="BINOS_ROOT to use, if not specified use $BINOS_ROOT")
    parser.add_option("-e", "--email", dest="email", help="Email Address")
    parser.add_option("-k", "--bugs", dest="bugs", help="Bugs fixed")
    parser.add_option("-v", "--valgrind", action="store_true",
                      dest="valgrind", help="Run valgrind")
    parser.add_option("-l", "--latest", action="store_true",
                      dest="latest", help="Run with latest code base")
    parser.add_option("-p", "--new-code", action="store_true",
                      dest="newcode", help="Run with new code base")
    parser.add_option("-n", "--no-attachment", action="store_true",
                      dest="no_attach", help="Do not attach results file")
    parser.add_option("-f", "--cflow", action="store_true", dest="cflow", 
                      help="Build with cflow enabled")
    parser.add_option("-s", "--skip", action="store_true", dest="skip", 
                      help="Skip clean and build, directly run tests")
    parser.add_option("-c", "--cdets", dest="cdets", help="CDETS attachment")
    parser.add_option("-r", "--after-run", action="store_true",
                      dest="after_run", help="skip clean after run")

    asic = "DopplerCS"
    binos_root = ''
    valgrind = False
    email = os.environ['USER'] + "@cisco.com"
    bugs = ''
    new_code = False
    no_attach = False 
    skip = False
    cflow = False
    cdets = ""
    after_run = False
    
    (options, args) = parser.parse_args()

    if options.email:
        email = options.email
    if options.bugs:
        bugs = options.bugs

    if options.valgrind:
        valgrind = True

    if options.skip:
        skip = True

    if options.cflow:
        cflow = True

    if options.asic:
        asic = options.asic

    if options.newcode:
        new_code = True 

    if options.no_attach:
        no_attach = True 

    if options.cdets:
        cdets = options.cdets 
        print("SDK regression results will be attached to %s" % (cdets))

    if options.after_run:
        after_run = options.after_run
        
    if options.binosroot:
        binos_root = options.binosroot
        os.environ['BINOS_ROOT'] = binos_root
    else:
        try:
            binos_root = os.environ['BINOS_ROOT']
        except KeyError:
            print("ERROR: BINOS_ROOT is not set")
            sys.exit(1)

    if options.latest:
        print("****************************************************************")
        print("** !! Attention !!                                            **")
        print("** Running with latest code could cause merge conflicts       **")
        print("** The workspace on which the regression is run will be       **")
        print("** affected. You need to run the regression again after       **")
        print("** fixing the conflicts.                                      **" )
        print("****************************************************************")
        try:
            resp = raw_input("Do you want to proceed [y/n] ")
        except KeyboardInterrupt:
            sys.exit(1)
        if resp.lower() in ('yes', 'y'):
            conflicts = updateWorkspace(binos_root)
            print("Number of merge conflicts: %d" % (conflicts))
            if conflicts >= 0:
                print("!!! There are %d merge conflicts !!!" % (conflicts))
                print("!!! Rerun the regression after fixing the conflicts !!!")

    date = datetime.datetime.now()

    print("BINOS_ROOT:", binos_root)
    print("ASIC:", asic)
    print("Email:", email)
    sys.stdout.flush()

    os.chdir(binos_root)
    start_time = time.time()

    # Setup the build environment for 64bit builds.
    # Run test and send email with the results.
    # Run Valgrind and it will be attached with the email
    # Code coverage will be done separately
    env = (binos_root, asic, new_code, no_attach, cflow)
    if not skip:
        cleanAndBuild(env, False)

    # Run without Valgrind
    tool = (False, False)
    results = runTest(env, tool) 
    emailTestResults(env, tool, results, email, bugs, cdets, start_time)

    if not after_run:
        cleanWorkspace(env)
    
    # Run with Valgrind
    if valgrind:
        tool = (True, False)
        results = runTest(env, tool) # run with valgrind
        emailTestResults(env, tool, results, email, bugs, cdets, start_time)


if __name__ == '__main__':
    main()
