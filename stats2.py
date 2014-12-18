import re

regex = re.compile(r' \[.*?\] (.*)')
f = open('pylint_reddit_report.parse', 'r')
f2 = open('mm_analysed.csv', 'r')

# (.*?):(\d+): \[(.*?)\] (.*)

code_dict = {}
rfp_dict = {}

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

        code = code[0]

        if code in code_dict :
            code_dict[code] += 1
        else :
            code_dict[code] = 1

    except :
        pass


for i, line in enumerate(f2.readlines()):
    sp = line.split(',')
    if sp[6] :
        sp[3] = sp[3][0]
        if sp[3] in rfp_dict :
            rfp_dict[sp[3]] += int(sp[6])
        else :
            rfp_dict[sp[3]] = int(sp[6])
        

#print(rfp_dict)

#for i in sorted(code_dict.items(), key=lambda x : x[1], reverse=True):
#    print('{} & {} & {:.2f}\% &  \\\\'.format(i[0], i[1], (rfp_dict[i[0]]/i[1]) * 100 ))
#    print('\\hline')

for i in sorted(code_dict.items(), key=lambda x : x[1], reverse=True):
    total = i[1]
    false_pos = 0
    if i[0] in rfp_dict :
        false_pos =  i[1] - rfp_dict[i[0]]
    print((i[0], (float(false_pos)/total), total))
