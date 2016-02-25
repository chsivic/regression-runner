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


if __name__ == "__main__":
    WS_NAME = "mac_" + datetime.datetime.now().strftime('%Y-%m-%d')
    try:
        retcode = subprocess.call("iws -l latest -t " + WS_NAME +
                   " -xe macallan_dev -d /scratch/siche/", shell=True)
        print "iws returned %s" % (retcode)

        WS_NAME = "iws_" + WS_NAME
        WS_DIR = "/scratch/siche/"+WS_NAME
        os.chdir(WS_DIR)
        BINOS_ROOT=os.getcwd()+"/binos"

        build_env = os.environ.copy()
        build_env["PATH"] = build_env["PATH"] + ":/auto/binos-tools/bin/"
        build_env["BINOS_ROOT"] = BINOS_ROOT
        
        if not grep(BINOS_ROOT+"/BUILD_LOGS/", 'SUCCESS.*build_x86_64_binos_root'):
            os.chdir("ios/sys")
            retcode = subprocess.call("mcp_ios_precommit build_x86_64_binos_root",
                                      env=build_env,
                                      shell=True)
            print "mcp_ios_precommit returned %s" % retcode

        build_env["INSTALL_DIR_PATH"] = BINOS_ROOT
        subprocess.call(["python", BINOS_ROOT + "/platforms/ngwc/doppler_sdk/tools/scripts/spectra_build.py",
                        "-p", "-a DopplerD"]);

    except subprocess.CalledProcessError as e:
        print "CalledProcessError", e
    except OSError as e:
        print >>sys.stderr, "Execution failed:", e
