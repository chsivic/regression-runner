#!/router/bin/python
from __future__ import print_function
import datetime, subprocess, os, sys, shutil
import re
import smtplib
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum

def pattern_exists_in_dir(path, content_pattern, fname_pattern=''):
    content_regObj = re.compile(content_pattern)
    fname_regObj = re.compile(fname_pattern) if fname_pattern else None
    for root, dirs, fnames in os.walk(path):
        for fname in fnames:
            if not fname_regObj or fname_regObj.search(fname):
                for line in open(root+'/'+fname, 'r'):
                    if content_regObj.search(line):
                        print(fname)
                        print(line)
                        return True
    return False

def find_files_in_dir(path, regex):
    regObj = re.compile(regex)
    matched = []
    for root, dirs, fnames in os.walk(path):
        matched += [f for f in fnames if regObj.match(f)]
    return matched

class Workspace (object):
    ws_path = ''
    binos_root = ''
    label = ''
    spectra_dir = ''
    def __repr__ (self) :
        return "<Workspace (%s) at %s>" % (self.label if self.label else self.branch, self.ws_path)

    def __init__(self, directory, branch = 'macallan_dev'):
        self.ws_path = directory
        self.branch = branch
        self.binos_root = "%s/binos" % self.ws_path if self.ws_path != '' else ''
        self.spectra_dir = self.binos_root + '/platforms/ngwc/doppler_sdk/spectra/'

    def pull (self):
        """Pull work space"""
        if self.branch == '': 
            raise ValueError("Branch is not set")
        if self.ws_path == '':
            raise ValueError("workspace dir is not set")

        try:
            parent, ws_dir = self.ws_path.rsplit('/', 1)
            cmd = "iws -l latest -t %s -xe %s -d %s" % (ws_dir, self.branch,
                                                        "/scratch/siche/")
            print("Executing (%s)" % (cmd))
            subprocess.check_call(
                cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                print ("iws returned 1")
            elif e.returncode != 255:
                print("###Error in pulling workspace", e.returncode)
                raise
        self.ws_path = "%s/%s" % (parent, "iws_"+ws_dir)
        self.binos_root = "%s/binos" % self.ws_path if self.ws_path != '' else ''
        self.spectra_dir = self.binos_root + '/platforms/ngwc/doppler_sdk/spectra/'

    def get_label(self):
        """
            read .acme_project label from .ACMEROOT/ws.lu
            cat .ACMEROOT/ws.lu
            binos macallan_dev/1174
            .acme_project macallan_dev/1144
            wcm macallan_dev/15
            ios macallan_dev/110
        """
        if self.label:
            return self.label
        try:
            with open("%s/%s" % (self.ws_path, ".ACMEROOT/ws.lu")) as f:
                for l in f.read().splitlines() :
                    if ".acme_project" in l:
                        self.label = l.split(' ')[1]
                        break
        except IOError as e:
            self.label = ''
        return self.label
            
    def build (self, target = 'x86_64_binos_root'):
        if pattern_exists_in_dir('%s/BUILD_LOGS/' % self.binos_root,
                'SUCC.*x86_64_binos_root'):
            print('x86_64_binos_root already built')
            return

        cmd = "mcp_ios_precommit -- -j16 build_x86_64_binos_root"
        print("Executing (%s)" % (cmd))
        try:
            os.chdir("%s/ios/sys" % (self.ws_path))
            subprocess.check_call(
                cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            print("###Error in building binos linkfarm")
            # Send email for build failure
            send_email_binos_root(email, self.binos_root, bugs_file)
        except Exception as ex:
            template = "An exception of type {0} occured. Arguments:\n{1!r}"
            message = template.format(type(ex).__name__, ex.args)
            print(message)

    def get_wireless_testcases(self):
        return [w.replace('.py', '') for w in 
            find_files_in_dir(self.spectra_dir + '/scripts/test_suite/Wireless/',
                                 '.*.py$')]
    def get_bugs_info(self, last_label):
        '''
        Get the DDTSs fixed between the current label and last label.
        '''
        bugs_info = ''
        if not self.label:
            self.get_label()
        cmd = 'acme refpoint_list -start_ver %s -end_ver %s -comp .acme_project' % \
                  (last_label, self.label)
        try:
            os.chdir(self.ws_path)
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError:
            print("#### acme command to get workspace info failed")
            return ''
    
        bugs_info += "Current label: %s Latest Label: %s\n" % (self.label, last_label)
        for line in output.splitlines():
            if "Change ID:" in line:
                bugs_info += line.split(':')[1].rstrip() + '  by '
            if "Created By:" in line:
                bugs_info += line.split(':')[1].rstrip() + '\n'
                
        return bugs_info


class Spectra(object):
    ws = None
    asic = ''
    def __init__(self, asic, ws):
        self.ws = ws
        self.asic = asic

    def build(self):
        if self.ws is None or self.asic == '':
            raise Exception('workspace not set')

        binos_root = self.ws.binos_root
        # Check old build log
        if os.path.isfile("%s/logs/build.%s.log" % (self.ws.spectra_dir, self.asic)):
            print("build.%s.log exist. Skip build" % (self.asic,))
            return
        
        # Now build spectra
        buildCmd = [binos_root + "/platforms/ngwc/doppler_sdk/tools/scripts/spectra_build.py", "-p",
                    "-a", self.asic, "-b", binos_root]
        try:
            print("Executing (%s)" % ' '.join(buildCmd))
            subprocess.check_call(buildCmd)
        except subprocess.CalledProcessError as e:
            print("#### Spectra build failed", e.returncode)
   
    def clean(self):
        if self.ws is None or self.asic == '':
            raise Exception('workspace not set')

        binos_root = self.ws.binos_root
        buildCmd = [binos_root + "/platforms/ngwc/doppler_sdk/tools/scripts/spectra_build.py", "-p",
                    "-a", self.asic, "-b", binos_root, '-co']
        try:
            subprocess.check_call(buildCmd)
        except subprocess.CalledProcessError as e:
            print("#### Spectra clean failed", e.returncode)
 
class Mode(Enum):
    DEFAULT = 1
    FEATURE = 2
class RegressionRunner(object):
    ws = None
    spectras = None
    test_runner_exe = "/ws/siche-sjc/macallan/test_runner.py"
    def __init__(self, ws=None, spectras=None):
        self.spectras = spectras

    def patch_ws (self):
        if self.ws is None:
            raise Exception('workspace not set')
        os.chdir(self.ws.ws_path)
        cmds = ('patch -p1 -f < /ws/siche-sjc/macallan/WiredToWirelessBridging_CS.stanley.diff',
                'patch -p1 -f < /ws/siche-sjc/macallan/wireless_spectra.diff',
                'patch -p1 -f < /ws/siche-sjc/macallan/spectra_scripts.diff')
        
        for cmd in cmds:
            try:
                subprocess.call(cmd, stderr=subprocess.STDOUT, shell=True)
            except subprocess.CalledProcessError as e:
                print("Error: ", e)
    def prepare_ws(self):
        if self.ws is None:
            raise Exception('workspace not set')

        print("Workspace: {}".format(self.ws))
        self.ws.pull()
        self.ws.build()
        
        self.patch_ws()
    def cleanup_results(self):
        binos_root = self.ws.binos_root
        scripts_dir = "{}/platforms/ngwc/doppler_sdk/spectra/scripts".format(binos_root)
        # If there are any core files in the directory then remove it
        # before running the test.
        for filename in os.listdir(scripts_dir):
            path = os.path.join(scripts_dir, filename)
            if not os.path.isfile(path):
                continue
            if "core" in filename.lower():
                os.remove(path)

        results_dir = "{}/platforms/ngwc/doppler_sdk/spectra/results".format(binos_root)
        # Remove the results directory and created it before each run
        if os.path.exists(results_dir):
            shutil.rmtree(results_dir)
        os.makedirs(results_dir)

    def run_test(self, asic = 'DopplerD', tests = [], mode=Mode.FEATURE):
        cmd = [self.test_runner_exe, '-p', '-a', asic,
            '-t', ':'.join(tests), 
            '-b', self.ws.binos_root]
        if mode is Mode.FEATURE : cmd += ['-r', '"TESTMODE=FEATURE"']
        print("\nExecuting(%s)" % ' '.join(cmd))
        try:
            output = ''
            p = subprocess.Popen(cmd, stdout = subprocess.PIPE, bufsize=1, 
                      universal_newlines=True)
            with p.stdout:
                for line in iter(p.stdout.readline, b''):
                    print(line, end='')
                    output += line
            p.wait()
        except subprocess.CalledProcessError as e:
            print("#### test_runner error: %s" % e)
     
        return output

    @staticmethod
    def get_wireless_testcases_from_csv ():
        implemented_testcases = []
        with open("/ws/siche-sjc/macallan/Wireless-Test-Plan.2016.csv") as f:
            for line in f:
                words = line.split(',')
                if words[3] != "MISSING":
                    implemented_testcases.append(words[2])
        return implemented_testcases

    @staticmethod
    def parse_test_runner_output (output):
        """
        Convert text output to test results in a dict
        """
        results = {}
        if "Results" not in output:
            return None
        output = output.split('Results')[1]
        for l in output.split('\n'):
            if '|' in l:
                key, result = l.split('|')[1:3]
                results[key.strip()] = result.strip()
        return results

class Reporter (object):
    emails = []
    def __init__(self, emails = []):
        self.emails = emails

    def send_email(self, subject, body):
        '''
        Construction an email message and send it to the email
        address provided. This function will get the workspace
        information and other information to construct the
        email.
        '''
        smtp_inst = smtplib.SMTP('localhost')
        for email in self.emails :
            outer = MIMEMultipart()
            outer['To'] = email
            outer['From'] = os.environ['USER'] + "@cisco.com"
            outer['Subject'] = subject 
        
            outer.attach(MIMEText(body, "plain"))
            composed = outer.as_string()
            smtp_inst.sendmail(email, email, composed)

        smtp_inst.quit()
    
    def compose(self, results, ws=None):
        body = ''
        for asic,res in results.items():
            results[asic] = {k:'OK' if v == 'PASSED' else v for k,v in res.items()}

        stats = {asic:sum(1 for res in results[asic].values() if res == 'OK')
            for asic in results.keys()}
        summary_format = "{:<10} : {:6}/{:5}\n"
        body += "Summary:\n" + summary_format.format('ASIC', 'Passed', 'Total')
        body += ''.join(
            [summary_format.format(asic, stats[asic], len(results[asic].keys()))
            for asic in results.keys()]) + '\n'

        if ws:
            body += "Workspace: "+repr(ws) + '\n'
#            body += ws.get_bugs_info("macallan_dev/1140")

        # FIXME merge keys from multiple results[asic]
        testcases = results[results.keys()[0]].keys()
        testcases.sort()
        tbl_format = '| {:<45} | {:<25} | {:<25} |\n'
        body += tbl_format.format('Testname', 'DopplerCS', 'DopplerD')
        body += ''.join([tbl_format.format(t, results['DopplerCS'][t],
                                             results['DopplerD'][t]) for t in testcases])
    
        body += """
        All tests were run with new code, feature mode.
        """

        return body

def run():
    STORAGE = '/scratch/siche'
    WS_NAME = "mac_" + datetime.datetime.now().strftime('%Y-%m-%d')
    EMAIL = 'staff.mayc@cisco.com'
#    WS_NAME = 'macd_2016-02-28'
#    EMAIL = 'siche@cisco.com'

    r = RegressionRunner();
    r.ws = Workspace(directory = "%s/%s" % (STORAGE, WS_NAME))
    r.prepare_ws()

    spectras = [Spectra(asic = 'DopplerD', ws = r.ws), 
                Spectra(asic = 'DopplerCS', ws = r.ws)]
    map(lambda sp: sp.build(), spectras)
    r.spectras = spectras

    results = {asic:r.parse_test_runner_output(
                    r.run_test(asic, r.ws.get_wireless_testcases()))
        for asic in ['DopplerCS', 'DopplerD']}

    reporter = Reporter(emails=[EMAIL])
    reporter.send_email("Wireless Regression Multi-Doppler Results",
                 reporter.compose(results, r.ws))
    
    shutil.rmtree(r.ws.ws_path)

if __name__ == "__main__":
    run()
