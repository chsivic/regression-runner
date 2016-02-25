#!/usr/bin/env /router/bin/python-2.7.4
'''
This python script is a wrapper script to execute the test case in spectra.
This script does not have any assumption about the environment
setting done by the user. Instead it will set the environ required for the
script to execute for a given asic family. It will also stage the DVPP 
libraries and executables for the DVPP for the asic family. This script 
will ignore the tests which are not valid for a given asic family by checking
the regression file for each asic family. This wrapper will also execute
the same test case on all asic families in single invocation.

Usage:
run_test.py -a <asic> -d <dvpp_release> -t <test> -r <run_opts> -l <log_file> 
Output:
    Default log file if (-l) option is not used:
    spectra/logs/log.<asic>.<test>.log

July 2014, Manas Pati

Copyright (c) 2014-2015 by Cisco Systems, Inc.
All rights reserved.
'''
import os
import sys
import platform
import re
import shutil
from optparse import OptionParser
import subprocess
import xmlrpclib
from SimpleXMLRPCServer import SimpleXMLRPCServer
import time

supported_asics = ["CS", "D", "G", "GStub", "E", "DL"]

#############################################################
# The dvpp_rel_info is organized per ASIC with the following
# information:
# [0]: prefix path to the general Dvpp releease
# [1]: dvpp release version
# [2]: patch release for a given dvpp release if applicable.
#      "" means no patch release.
# [3]: name of the CIMA executable
#############################################################
dvpp_rel_info = {
    "CS": ("/auto/dopplercs_cima/releases/paq/RELEASE/DvppInfra",
           "dopplercs_cima_S0101_R2014_07_27",
           "",
           "DopplercsMdlPaq_64BIT"),
    "D": ("/auto/dopplerd/releases/paq/DvppInfra",
          "dopplerd_T0097_2_R2015_07_01",
          "P1_R2015_07_02",
          "DopplerDMdlPaq_64BIT"),
    "G": ("/auto/dopplerg/releases/paq/DvppInfra",
          "dopplerg_T0071_R2015_07_30",
          "",
          "DopplerGMdlPaq_64BIT"),
    "GStub": ("/auto/dopplerg/releases/paq/DvppInfra",
              "dopplerg_T0071_R2015_07_30",
              "",
              "DopplerGMdlPaq_64BIT"),
    "E": ("/auto/dopplere/releases/paq/DvppInfra",
          "dopplere_S1347_R2015_12_01_P2",
          "",
          "DopplerEMdlPaq_64BIT"),
    "DL": ("/auto/dopplerdl/releases/paq/DvppInfra",
          "dopplerdl_S0010_R2015_09_30",
          "",
          "DopplerDMdlPaq_64BIT")
}

dvpp_rel_libs = ["paqobjs", "cima_objs", "gcmobjs", "kgenobjs"]

spectra_libs = ["ngwcutils", "sdm", "rm_common", "rm_iml", "rmc",
                "rms", "afd", "ral", "sdm", "spectraapp",
                "spectrainfra", "spectra_swig"]

spectra_libs_new = ["asd2", "cad"]

#############################################################
# None datapath tests have different executables and cmd
# line paramaters. Some takes ASIC as parameter and some
# does not. Hence, the following tupple is used to specify
# that. (python, location, executable, cmdline, asic_specific, logfile)
#############################################################
non_dp_tests = {
    "aalUT" : (True, "/usr/binos/lib", "aal_test_runner.py", "-a ", True, "aal_ut.log"),
    "capUT" : (True, "/usr/binos/lib", "cap_test_runner.py", "-a", True, "cap_ut.log"),
    "spectraUT" : (True, "/usr/binos/lib", "spectra.py", "-a ", True, "spectra_ut.log"),
}

def get_dvpp_dir(asic, dvpp_rel):
    '''
    Get the DVPP release directory for the dvpp release.
    '''
    if (dvpp_rel == dvpp_rel_info[asic][1]) and dvpp_rel_info[asic][2]:
        return '%s/%s/so64_dvpp/%s' % \
            (dvpp_rel_info[asic][0], dvpp_rel, dvpp_rel_info[asic][2])
    else:
        return '%s/%s/so64_dvpp' % (dvpp_rel_info[asic][0], dvpp_rel)


def get_dvpp_exec_path(asic, dvpp_rel):
    '''
    Get the DVPP release directory for the dvpp release.
    '''
    if (dvpp_rel == dvpp_rel_info[asic][1]) and dvpp_rel_info[asic][2]:
        return '%s/%s/so64_dvpp/%s/%s' % \
            (dvpp_rel_info[asic][0], dvpp_rel, dvpp_rel_info[asic][2], \
             dvpp_rel_info[asic][3])
    else:
        return '%s/%s/so64_dvpp/%s' % \
            (dvpp_rel_info[asic][0], dvpp_rel, dvpp_rel_info[asic][3])


def get_dvpp_exec_name(asic):
    '''
    Get the DVPP release executable name for a given asic.
    '''
    return dvpp_rel_info[asic][3]


def get_sdk_root(binos_root):
    '''
    Get the Doppler SDK root from the BINOS_ROOT.
    '''
    return '%s/platforms/ngwc/doppler_sdk' % (binos_root)


def get_spectra_root(binos_root):
    '''
    Get the Doppler SDK spectra root from the BINOS_ROOT.
    '''
    return '%s/platforms/ngwc/doppler_sdk/spectra' % (binos_root)

def get_linkfarm(binos_root):
    '''
    Get the linkfarm used for the spectra from the BINOS_ROOT.
    '''
    return '%s/linkfarm/x86_64' % (binos_root)

def get_linkfarm_asic(binos_root, asic):
    '''
    Get the linkfarm used for the spectra from the BINOS_ROOT.
    '''
    return '%s/linkfarm/x86_64-spectra%s' % (binos_root, asic)


def sanity_check_dvpp_release(asic, dvpp_rel):
    '''
    Check the DVPP release executable and libraries present in the
    provided dvpp_release. If required information not found then the
    test can not run.
    '''
    if not os.path.exists(get_dvpp_dir(asic, dvpp_rel)):
        print 'ERROR: DVPP release %s does not exist' % (dvpp_rel)
        return False

    for dvpp_lib in dvpp_rel_libs:
        if not os.path.exists('%s/so64_%s' %
                              (get_dvpp_dir(asic, dvpp_rel), dvpp_lib)):
            print 'ERROR: DVPP library %s missing' % (dvpp_lib)
            return False
    
    if not os.path.exists(get_dvpp_exec_path(asic, dvpp_rel)):
        print 'ERROR: DVPP executable missing'
        return False

    return True


def sanity_check_build(binos_root, asic, port_mode):
    '''
    Check whether the build for the asic is done properly.
    '''
    libs_check = spectra_libs
    if port_mode:
        libs_check += spectra_libs_new

    for spectra_lib in libs_check:
        if not os.path.exists('%s/usr/binos/lib/lib%s.so' %
                              (get_linkfarm_asic(binos_root, asic), spectra_lib)):
            print 'ERROR: spectra library is missing (%s)' % (spectra_lib)
            return False

    return True


def link_dvpp_exec(binos_root, asic, dvpp_rel):
    '''
    Link the DVPP executable with the spectra asic linkfarm.
    If the link already exists then remove it before linking
    to the new one.
    '''
    if not os.path.exists('%s/usr/binos/bin' % (get_linkfarm_asic(binos_root, asic))):
        os.chdir('%s/usr/binos' % (get_linkfarm_asic(binos_root, asic)))
        os.system("mkdir -p bin")

    os.chdir('%s/usr/binos/bin' % (get_linkfarm_asic(binos_root, asic)))
    if os.path.exists(get_dvpp_exec_name(asic)):
        os.remove(get_dvpp_exec_name(asic))
    os.symlink(get_dvpp_exec_path(asic, dvpp_rel),
               get_dvpp_exec_name(asic))


def set_ld_path(binos_root, asic, dvpp_rel, quiet):
    '''
    Get the LD_LIBRARY_PATH for the asic linkfarm and the DVPP release.
    LD_LIBRARY_PATH contains the default linkfarms for all the binos
    execs. We also need to add all librarry paths used in spectra.
    '''
    ld_paths = ['%s/linkfarm/x86_64/usr/lib' % (binos_root),
                '%s/linkfarm/x86_64/usr/binos/lib' % (binos_root),
                '%s/linkfarm/x86_64-spectra%s/usr/binos/lib' % (binos_root, asic),
                '%s/linkfarm/x86_64/usr/lib64' % (binos_root),
                '%s/linkfarm/x86_64/usr/binos/lib64' % (binos_root),
                '%s/linkfarm/x86_64-spectra%s/usr/binos/lib64' % (binos_root, asic),
                '%s/usr/binos/lib' %(binos_root),
                '%s/usr/lib' %(binos_root)]
    for dvpp_lib in dvpp_rel_libs:
        ld_paths.append('%s/so64_%s' %
                (get_dvpp_dir(asic, dvpp_rel), dvpp_lib))

    ld_lib_path = ':'.join(ld_paths)
    os.environ['LD_LIBRARY_PATH'] = ld_lib_path
    # Note, the INSTALL_DIR_PATH is not required anymore but there are some
    # old dvpp release where it checks the INSTALL_DIR_PATH hence make sure
    # it is set otherwise there will be assert in DVPP executable. We will
    # remove it soon.
    os.environ['INSTALL_DIR_PATH'] = '%s/platforms/ngwc/doppler_sdk/spectra' % (binos_root) 
    if not quiet:
        print 'LD_LIBRARY_PATH: %s' % (os.environ['LD_LIBRARY_PATH'])


def get_dvpp_exec_from_linkfarm(binos_root, asic):
    '''
    Get the executable from the linkfarm for the asic.
    '''
    return '%s/linkfarm/x86_64-spectra%s/%s' % \
        (binos_root, asic, get_dvpp_exec_name(asic))

def get_test_cases_from_list(test_case_list):
    test_cases = []

    for line in test_case_list:
        if "," in line or ";" in line:
            if "COMMIT" in line:
                line_temp = line.split('+')[0]
                line = line_temp+','
            if "TESTNAME" in line:
                temp_line = line.split('"')[1]
                line = temp_line
            if ";" in line:
                line = line.replace(';', ',')
            if "_list" in line:
                pass
            elif "#" in line or 'AAL_' in line or 'FEATURE_' in line:
                pass
            elif "TESTNAME" in line:
                test_cases += line+'&&&&'
            elif "_" not in line:
                position = line.find(',')
                test_cases += ((line[:position])+'&&&&')
            elif "_" in line:
                test_cases += (line.split("_")[0])
                run_opts_temp = line.split('"')
                if len(run_opts_temp)>1:
                    test_cases += ('@'+run_opts_temp[1]+'&&&&')

    test_cases = ''.join(test_cases)
    test_cases = test_cases[:-4]
    test_cases = test_cases.split('&&&&')
    
    return test_cases

def get_regress_file_from_asic(asic, binos_root):
    if asic=='CS':
        regress_file = '%s/scripts/dopplercs_paq.regress' %(get_spectra_root(binos_root))
    elif asic=='D':
        regress_file = '%s/scripts/dopplerd_paq.regress' %(get_spectra_root(binos_root))
    elif asic=='E':
        regress_file = '%s/scripts/dopplere_paq.regress' %(get_spectra_root(binos_root))
    else:
        regress_file = ""
    
    return regress_file

def locate_testcase (root, testname):
    for root, dirs, files in os.walk(root):
        if '.CC' in root: continue
        if testname+'.py' in files:
            return True
    return False
                

def process_log_file (log_file):
    result = "FAILED"
    f = open(log_file)
    for line in f:
        if "Mismatch in packets sent and received" in line:
            result = "FAILED - PACKET_MISMATCH"
            break
        if "Can't find test" in line:
            result = "FAILED - MISSING"
            break
        if "Simulation PASSED" in line:
            result = "PASSED"
            break
    f.close()
    return result
 
def get_test_cases_in_suite(test_suite, regress_file):
    '''
    Parse the regression file and get the test_suites present in it.
    Then get the test cases and associated runOpts for the test case.
    '''
    if not os.path.exists(regress_file):
        return test_cases;

    inputfile = open(regress_file, 'r')
    test_suite_found = False
    test_list = []

    for line in inputfile:
        if not test_suite_found:
            if test_suite in line and  '=' in line and line.split(test_suite,1)[1][0] == ' ':
                test_suite_found = True
                print "Found test_suite %s" % line.split('=',1)[0]
        else:
            line = line.replace('\n', '')
            if len(line) > 0:
                test_list.append(line)
            else:
                break

    return get_test_cases_from_list(test_list)

def main():
    '''
    Main parse routines for Test runner.
    '''
    parser = OptionParser(usage="usage: %prog\n"
                          "-d <dvpp_release> \n"
                          "-t <test_names> \n"
                          "-f <File containing test_names>"
                          "-z <entire_regression> \n"
                          "-s <test_suite> \n"
                          "-c <commit_regression> \n"
                          "-r <run_opts_for_test> \n"
                          "-b <binos_root> \n"
                          "-a <asic> \n"
                          "-l <logfile>\n"
                          "-p <newportedcode>\n"
                          "-e <EIO_cosim>\n" 
                          "-i <ip address of UCS running Cima>\n"
                          "-n <port number Cima sniffs on>\n"
                          "-q <quiet>\n",
                          description="Spectra Test Runner")

    parser.add_option("-t", "--test-cases", dest="testcases",
                      help="Test case with separator (:) such as L2Basic:L3Basic")
    parser.add_option("-f", "--file-test-cases", dest="file_testcases",
                      help="File containing Test case with separator (:) such as L2Basic:L3Basic")
    parser.add_option("-z", "--whole-regression", dest="regression",
                      help="Runs entire regression")
    parser.add_option("-s", "--test-suite", dest="testsuite",
                      help="Test suite name with separator. If this option is \
                  is used then the -t option is ignored as it is \
                  redundant. Also, check the commit regression option\
                  -c for controlling the test execution.")
    parser.add_option("-c", "--commit-regression", action="store_true",
                      dest="commitregression",
                      help="Run commit regression tests from test suite.\
                  Used with the -s options.")
    parser.add_option("-d", "--dvpp-release", dest="dvpprelease",
                      help="DVPP release location. Only required for first time \
                  or overwriting the existing DVPP information. If not \
                  specified then the latest stable release is picked up\
                  from DVPP release.")
    parser.add_option("-r", "--run-opts", dest="runopts",
                      help="Opaque run Opts passed directly to the test")
    parser.add_option("-a", "--asic-version", dest="asicversion",
                      help="One or multiple asic versions. Such as DopplerCS:DopplerD")
    parser.add_option("-b", "--binos-root", dest="binosroot",
                      help="BINOS_ROOT to use, if not specified use $BINOS_ROOT")
    parser.add_option("-l", "--log-file", dest="logfile",
                      help="log file specified")
    parser.add_option("-q", "--quiet", action="store_true",
                      dest="quiet", help="Run tests quiet mode")
    parser.add_option("-p", "--port", action="store_true",
                      dest="port", help="Run tests with ported code")
    parser.add_option("-e", "--eio", action="store_true",
                      dest="eio_cosim", help="Run tests in cosim environment")
    parser.add_option("-i", "--ip", dest="cima_ip", help="ip of UCS running Cima")
    parser.add_option("-n", "--portNumber", dest="port_number", 
                    help="port number that UCS listens on")
    (options, args) = parser.parse_args()

    binos_root = ''
    asic = ''
    dvpp_rel = ''
    run_opts_loop = ''
    test_suites = []
    test_cases = []
    commit = False
    log_file_opt = ""
    quiet_mode = False
    port_mode = False
    eio_cosim_flag = False 
    cima_ip_address = ""
    cima_port_number = ""
    CimaProxy = None 

    if options.logfile:
        log_file_opt = options.logfile

    if options.quiet:
        quiet_mode = True 

    if options.port:
        port_mode = True 
    
    if options.eio_cosim:
        print "Running in EIO cosim mode"
        eio_cosim_flag = True
        if options.cima_ip and options.port_number:
            cima_ip_address = options.cima_ip
            cima_port_number = options.port_number
            url = "http://" + cima_ip_address + ":" + cima_port_number + "/"
            CimaProxy = xmlrpclib.ServerProxy(url, allow_none=True) 
        else:
            print "ERROR: UCS ip and port number not provided"
            sys.exit(1)

    if options.binosroot:
        binos_root = options.binosroot
        os.environ['BINOS_ROOT'] = binos_root
    else:
        try:
            binos_root = os.environ['BINOS_ROOT']
        except KeyError:
            print "ERROR: BINOS_ROOT is not set"
            sys.exit(1)

    if options.asicversion:
        asic = options.asicversion[7:]
        if asic not in supported_asics:
            print "ERROR: asic [%s] not supported" % (options.asicversion)
            sys.exit(1)
    else:
        print "ERROR: ASIC version not provided"
        sys.exit(1)

    if eio_cosim_flag == False and sanity_check_build(binos_root, asic, port_mode) == False:
        sys.exit(1)

    if not quiet_mode:
        print "Using BINOS_ROOT: %s" % (binos_root)

    exec_log_file = '%s/logs/run_test.log' % (get_spectra_root(binos_root))
    dvpp_file = '%s/.spectra%s-dvpp' % (get_spectra_root(binos_root), asic)
    dvpp_exec = '%s/usr/binos/bin/%s' % \
            (get_linkfarm_asic(binos_root, asic), get_dvpp_exec_name(asic))

    if eio_cosim_flag == False:
        ##################################################################### 
        # If the DVPP release is provided in command line option use it.
        # If not provided if it was provided in earlier test cases. If
        # not use the standard stable release.
        ##################################################################### 
        if options.dvpprelease:
            dvpp_rel = options.dvpprelease
        else:
            if os.path.exists(dvpp_file):
                for line in open(dvpp_file):
                    dvpp_rel = line
                    break
            else:
                try:
                    d_path, dvpp_rel, patch_rel, d_exec = dvpp_rel_info[asic]
                except KeyError:
                    print "No stable DVPP release found"
                    pass

        if not quiet_mode:
            print "Using the DVPP release: %s" % (dvpp_rel)

        if sanity_check_dvpp_release(asic, dvpp_rel) == False:
            print "DVPP release %s not found" % (dvpp_rel)
            sys.exit(1)

        if not os.path.exists(dvpp_file):
            f = open(dvpp_file, 'w')
            f.write(dvpp_rel)
            f.close()
        else:
            old_dvpp_rel = ""
            for line in open(dvpp_file):
                old_dvpp_rel = line
                break
            if dvpp_rel != old_dvpp_rel:
                os.remove(dvpp_file)
                f = open(dvpp_file, 'w')
                f.write(dvpp_rel)
                f.close()
        link_dvpp_exec(binos_root, asic, dvpp_rel)

    if options.testsuite:
        test_suites = options.testsuite.split(':')
        regress_file = get_regress_file_from_asic(asic, binos_root)
        for test in test_suites:
            testcase = get_test_cases_in_suite(test,regress_file)
            print "Appending test from \'" + test + "\' testsuite" 
            test_cases.extend(testcase)
            
    elif options.testcases:
        test_cases = options.testcases.split(':')
    elif options.file_testcases:
        try:
            f = open(options.file_testcases, 'r')
            test_cases =f.read().split(':')
        except IOError as e:
            print 'ERROR: File not found : %s' % options.file_testcases
            sys.exit(1)

    elif options.regression:
        if asic=='CS':
            regress_file = '%s/scripts/dopplercs_paq.regress' %(get_spectra_root(binos_root))
        elif asic=='D':
            regress_file = '%s/scripts/dopplerd_paq.regress' %(get_spectra_root(binos_root))
        elif asic=='E':
            regress_file = '%s/scripts/dopplere_paq.regress' %(get_spectra_root(binos_root))
        elif asic=='DL':
            regress_file = '%s/scripts/dopplerd_paq.regress' %(get_spectra_root(binos_root))
        inputfile = open(regress_file, 'r')
        regress_lines = inputfile.readlines()
        line_number = 0
        run_opts_loop = '@'
        for line in regress_lines:
            line_number += 1
            if "," in line or ";" in line:
                if "COMMIT" in line:
                    line_temp = line.split('+')[0]
                    line = line_temp+','
                if "TESTNAME" in line:
                    temp_line = line.split('"')[1]
                    line = temp_line
                if ";" in line:
                    line = line.replace(';', ',')
                if "_list" in line:
                    pass
                elif "#" in line or 'AAL_' in line or 'FEATURE_' in line:
                    pass
                elif "TESTNAME" in line:
                    test_cases += line+'&&&&'
                elif "_" not in line:
                    position = line.find(',')
                    test_cases += ((line[:position])+'&&&&')
                elif "_" in line:
                    test_cases += (line.split("_")[0])
                    run_opts_temp = line.split('"')
                    if len(run_opts_temp)>1:
                        test_cases += ('@'+run_opts_temp[1]+'&&&&')
        test_cases = ''.join(test_cases)
        test_cases = test_cases[:-4]
        test_cases = test_cases.split('&&&&')
    else:
        print 'ERROR: test case are not provided'
        sys.exit(1)

    if len(test_cases) == 0:
        print 'No test case provided or found in the test suite'
        sys.exit(1)

    run_opts = ''
    if options.runopts:
        run_opts = options.runopts

    set_ld_path(binos_root, asic, dvpp_rel, quiet_mode)
    results = []
    
    for idx, test_case in enumerate(test_cases):
        test_passed = False
        if run_opts_loop=='@':
            run_opts = ''
        if '@' in test_case:
            test_case_temp = test_case.split('@')[0]
            run_opts = test_case.split('@')[1]
            test_case = test_case_temp
        if "TESTNAME" in test_case:
            temp_test_case = test_case.split()[0].replace('TESTNAME=', '')
            run_opts = test_case.replace(test_case.split()[0]+' ', '')
            test_case = temp_test_case
        if not log_file_opt:
            log_file = '%s/logs/%s.%s.%s.log' % (get_spectra_root(binos_root), 
                                              test_case, asic,
                                              "FEATURE" if "FEATURE" in run_opts
                                              else "")
        else:
            log_file = '%s/logs/%s'%(get_spectra_root(binos_root), log_file_opt)
        
        log_redirect = ' >> %s 2>&1' % (log_file)
        if os.path.exists(log_file):
            os.remove(log_file)
 
        if not locate_testcase(get_spectra_root(binos_root) +
                               "/scripts/test_suite", test_case): 
            print "Test %s doesn't exist" % test_case
            results.append((test_case, "FAILED - MISSING"))
            continue
        print "Running Test %s (%d/%d)" % (test_case, idx, len(test_cases))
        if test_case in non_dp_tests:
            ndp_python, ndp_loc, ndp_test, ndp_opts, ndp_asic, ndp_log = non_dp_tests[test_case]
            if ndp_python:
                if ndp_asic:
                    exec_cmd = '%s/usr/bin/python2.7 %s/%s/%s %s Doppler%s' % \
                            (get_linkfarm(binos_root), \
                            get_linkfarm_asic(binos_root, asic), \
                            ndp_loc, ndp_test, ndp_opts, asic)
                else:
                    exec_cmd = '%s/usr/bin/python2.7 %s/%s/%s %s' % \
                            (get_linkfarm(binos_root), \
                            get_linkfarm_asic(binos_root, asic), \
                            ndp_loc, ndp_test, ndp_opts)
            else: 
                if ndp_asic:
                    exec_cmd = '%s%s/%s %s Doppler%s' % \
                            (get_linkfarm_asic(binos_root, asic), \
                            ndp_loc, ndp_test, ndp_opts, asic)
                else:
                    exec_cmd = '%s%s/%s %s' % \
                            (get_linkfarm_asic(binos_root, asic), \
                            ndp_loc, ndp_test, ndp_opts)

            if ndp_log:
                log_redirect = ' >> %s 2>&1' % (ndp_log)
                if os.path.exists(ndp_log):
                    os.remove(ndp_log)

            os.system("%s %s" % (exec_cmd, log_redirect))
            check_file = True
            if ndp_log:
                try:
                    f = open("%s/logs/%s" % (get_spectra_root(binos_root), ndp_log))
                except IOError:
                    check_file = False
                    test_passed = False
            else:
                try:
                    f = open(log_file)
                except IOError:
                    check_file = False
                    test_passed = False
            if check_file:
                for line in f:
                    if "SUMMARY: PASSED" in line:
                        test_passed = True
                    if "FAILED (failures=" in line:
                        test_passed = False
                f.close()

        else:
            if eio_cosim_flag:
                exec_cmd = "python paq_main.py"
            else:
                exec_cmd = '%s/usr/binos/bin/%s' % \
                        (get_linkfarm_asic(binos_root, asic), get_dvpp_exec_name(asic))
            os.system("%s TESTNAME=%s %s %s" % (exec_cmd, test_case, run_opts, log_redirect))
            result = process_log_file(log_file)
            test_passed = True if result == "PASSED" else False
           
        if test_passed:
            print "- PASSED"
            results.append((test_case, "PASSED"))
        else:
            print "- FAILED"
            results.append((test_case, result))
        if eio_cosim_flag:
            CimaProxy.resetCima()
            # wait for Cima to be restarted
            print "Wait for Cima to be rerestted" 
            time.sleep(10)

    if eio_cosim_flag:
        CimaProxy.killCima()
    print
    print "Results Doppler%s Test Count: %d" % (asic, len(results))
    print "+---------------------------------------------------+"
    for test_case,result in results:
        print "| %-40s | %6s |" % (test_case, result)
    print "+---------------------------------------------------+"
    print

if __name__ == '__main__':
    main()
