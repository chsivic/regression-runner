#!/router/bin/python
from __future__ import print_function
import datetime, subprocess, os, sys
import re
import smtplib
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def find_pattern_in_dir(path, regex):
    regObj = re.compile(regex)
    for root, dirs, fnames in os.walk(path):
        for fname in fnames:
            for line in open(root+fname, 'r'):
                if regObj.search(line):
                    return True

def find_files_in_dir(path, regex):
    regObj = re.compile(regex)
    matched = []
    for root, dirs, fnames in os.walk(path):
        matched += [f for f in fnames if regObj.match(f)]
    return matched

class Workspace (object):
    def __repr__ (self) :
        return "<Workspace of branch %s at BINOS_ROOT=%s>" % (self.branch, self.binos_root)

    def __init__(self, directory = '', branch = 'macallan_dev'):
        self.ws_dir = directory
        self.branch = branch
        self.binos_root = "%s/binos" % self.ws_dir if self.ws_dir != '' else ''
        self.spectra_dir = self.binos_root + '/platforms/ngwc/doppler_sdk/spectra/'

    def pull (self):
        """Pull work space"""
        if self.branch == '': 
            raise ValueError("Branch is not set")
        if self.ws_dir == '':
            raise ValueError("workspace dir is not set")

        try:
            if not os.path.exists(self.ws_dir):
                os.makedirs(self.ws_dir)
            os.chdir(self.ws_dir)
            cmd = "acme nw -project %s -sb xe" % (self.branch)
            print("Executing (%s)" % (cmd))
            subprocess.check_call(
                cmd, stderr=subprocess.STDOUT, shell=True)
        except subprocess.CalledProcessError as e:
            if e.returncode != 255:
                print("###Error in pulling workspace", e.returncode)
                raise
            
    def build (self, target = 'x86_64_binos_root'):
        if find_pattern_in_dir('%s/BUILD_LOGS/' % self.binos_root,
                'SUCC.*x86_64_binos_root'):
            print('x86_64_binos_root already built')
            return

        cmd = "mcp_ios_precommit -- -j16 build_x86_64_binos_root"
        print("Executing (%s)" % (cmd))
        try:
            os.chdir("%s/ios/sys" % (self.ws_dir))
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
                                 '.*.py')]

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
 
class RegressionRunner(object):
    ws = None
    test_runner_exe = "/ws/siche-sjc/macallan/test_runner.py"
    def __init__(self, spectras=None):
        self.spectras = spectras

    def prepare_ws(self):
        if self.ws is None:
            raise Exception('workspace not set')

        print("Workspace: {}".format(self.ws))
        self.ws.pull()
        self.ws.build()

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

    def run_test(self, asic = 'DopplerD', tests = []):
        cmd = [self.test_runner_exe, '-p', '-a', asic,
            '-t', ':'.join(tests[5:7]), '-r', '"TESTMODE=FEATURE"',
            '-b', self.ws.binos_root]
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
                results[l.split('|')[1].strip()] = l.split('|')[2].strip()
    
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
    
    def compose(self, results):
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




def run():
    STORAGE = '/scratch/siche'
    WS_NAME = "mac_" + datetime.datetime.now().strftime('%Y-%m-%d')
    WS_NAME = 'gogogo'
    r = RegressionRunner();
    r.ws = Workspace(directory = "%s/%s" % (STORAGE, WS_NAME))
    r.prepare_ws()

    spectras = [Spectra(asic = 'DopplerD', ws = r.ws), 
                Spectra(asic = 'DopplerCS', ws = r.ws)]
#    map(lambda sp: sp.build(), spectras)
    r.spectras = spectras

    results = {asic:r.parse_test_runner_output(r.run_test(asic, r.ws.get_wireless_testcases()))
        for asic in ['DopplerCS', 'DopplerD']}

    r = Reporter(['siche@cisco.com'])

if __name__ == "__main__":
    run()
