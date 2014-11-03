import re

regex = re.compile(r' \[.*?\] (.*)')
f = open('pylint_reddit_report_no_W0611_no_W0614_no_C0301.parse', 'r')

# (.*?):(\d+): \[(.*?)\] (.*)

for i, line in enumerate(f.readlines()):
    try :
        line = line.rstrip()
        split = line.split(':')
        filename = split[0]
        nline = split[1]
        fin = split[2]
        m = re.match(regex, fin)
        inter_code = m.group(0)
        split_code = inter_code.strip().replace('[', '').replace(']', '').split(',')
        if(len(split_code) > 1):
            code = split_code[0].strip()
        else :
            code = split_code.strip()
        if(len(code.split(' ')) > 1):
            code = code.split(' ')[0]
        message = m.group(1)
        print('{},{},{},{},{}'.format(i+1, filename, nline, code, message))
    except :
        pass