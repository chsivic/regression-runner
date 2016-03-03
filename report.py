#!/users/siche/bin/python
import pickle
from test_runner import get_test_cases_in_suite

def collect_test_suites():
    l3_suites = ['Layer3Mtu', 'L3BasicAAL', 'Layer3Frag', 'Layer3Stats', 'Layer3Vrf',
              'Layer3Ipv6Negative', 'L3Ipv4GreDecap', 'L3BasicFEATURE',
              'L3Ipv6GreDecap', 'Layer3ECMP', 'Layer3Ipv6IDS', 'Layer3Span',
              'Layer3Basic', 'L3Ipv6GreEncap', 'Layer3Pbr', 'L3MulticastV4',
              'L3MulticastV6', 'L3Ipv4GreEncap', 'Layer3IPv6Basic',
              'Layer3Negative', 'Layer3NegativeSrc', 'Layer3Urpf']
    wl_suites = ['WirelessBasic', 'WirelessPuntingToCpu', 'WirelessMobility']
    suites={}
    regress_file = "/scratch/3/gogogo/binos/platforms/ngwc/doppler_sdk/spectra/scripts/dopplercs_paq.regress"
    suites['Wireless'] = {s:[t.split('@')[0] for t in
        get_test_cases_in_suite(s, regress_file)] for s in wl_suites}
    suites['Layer3'] = {s:[t.split('@')[0] for t in
        get_test_cases_in_suite(s, regress_file)] for s in l3_suites}
    
    with open('test_suites.pickle', 'w') as h:
        pickle.dump(suites, h)

def sum_by_suites():
    with open('test_suites.pickle', 'r') as h:
        suites = pickle.load(h)
    with open('test_results.gogogo.pickle', 'r') as h:
        results = pickle.load(h)

    results_cs = results['DopplerCS']
    suite_sum = {}
    for s,tests in suites['Layer3'].items():
        suite_sum[s] = (sum(1 for t in tests 
                            if t and t in results_cs.keys() and
                            'PASS' in results_cs[t]),
                        len(tests))
        print("%30s : %s" % (s, [t for t in tests
                                if t and t in results_cs.keys() and
                                'PASS' not in results_cs[t]]))
    return suite_sum

suite_sum = sum_by_suites()
for k,v in suite_sum.items():
    print("%30s : %2d/%2d" % (k, v[0], v[1]))
