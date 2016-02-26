#!/router/bin/python
import datetime, subprocess, os, sys

def grep(path, regex):
    import re
    regObj = re.compile(regex)
    for root, dirs, fnames in os.walk(path):
        for fname in fnames:
            for line in open(root+fname, 'r'):
                if regObj.search(line):
                    return True

class Workspace (object):
    def __init__(self, directory = '', branch = 'macallan_dev'):
        self.ws_dir = directory
        self.branch = branch
        self.binos_root = "%s/binos" % self.ws_dir if self.ws_dir != '' else ''

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
        if grep('%s/BUILD_LOGS/' % self.binos_root,
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
            print message

    def __repr__ (self) :
        return "<Workspace of branch %s at BINOS_ROOT=%s>" % (self.branch, self.binos_root)

class RegressionRunner(object):
    ws = None
    def prepare(self):
        if self.ws is None:
            raise Exception('workspace not set')

        print("Workspace: {}".format(self.ws))
        self.ws.pull()
        self.ws.build()


if __name__ == "__main__":
    STORAGE = '/scratch/siche'
    WS_NAME = "mac_" + datetime.datetime.now().strftime('%Y-%m-%d')
    WS_NAME = 'gogogo'
    r = RegressionRunner();
    w = Workspace(directory = "%s/%s" % (STORAGE, WS_NAME))
    r.ws = w;
    r.prepare()
    
