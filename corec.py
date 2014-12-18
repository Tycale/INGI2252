import re
from jinja2 import Template

regex = re.compile(r' \[.*?\] (.*)')
f = open('pylint_reddit_report.parse', 'r')

# (.*?):(\d+): \[(.*?)\] (.*)
dict_file = {}
code_set  = set()
file_set = set()
exclude_code = []

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
        
        if not filename in dict_file:
            dict_file[filename] = set()

        dict_file[filename].add(code)
        code_set.add(code)
        file_set.add(filename)
    except :
        pass

sorted_code = list(code_set)
sorted_code.sort()
#print sorted_code

sorted_file = list(file_set)
sorted_file.sort()
#print sorted_file

matrix = []

for code in sorted_code:
    temp = []
    for fn in sorted_file:
        if code in dict_file[fn]:
            temp.append(True)
        else:
            temp.append(False)
    matrix.append(temp)

def D(c1, c2):
    index_c1 = sorted_code.index(c1)
    index_c2 = sorted_code.index(c2)
    
    line_c1 = matrix[index_c1]
    line_c2 = matrix[index_c2]
    
    res1 = []
    res2 = []
    for i in range(len(line_c1)):
        res1.append(line_c1[i] != line_c2[i]) 

    for i in range(len(line_c1)):
        res2.append(line_c1[i] or line_c2[i])
    
    return float(sum(res1)) / float(sum(res2))


new_matrix = []

for code1 in sorted_code:
    temp = []
    for code2 in sorted_code:
        temp.append(D(code1, code2))
    new_matrix.append(temp)

#print new_matrix

total_code = len(sorted_code)
for code in sorted_code:
    pc = 0
    for k,v in dict_file.iteritems():
        if code in v:
            pc += 1
    pc = float(pc) / float(total_code)
    if pc > 0.9: 
        exclude_code.append(code)

print 'Excluded codes : ', exclude_code

tmpl = Template(u'''\
<!DOCTYPE html>
<html>
  <head>
    <title>Resultats</title>
  </head>
  <body>

  <table>
    <thead>
        <tr>
        <th>/</th>
        {%- for sc in sorted_code %}<th>{{ sc }}</th>{%- endfor %}
        </tr>
    </thead>
    <tbody>

    {%- for item in matrix %}
        {% set rowloop = loop %}
        <tr><td><b>{{ sorted_code[(loop.index)-1] }}</b></td>
        {% for item2 in item %}
        <td>
        {% if item2 <= 0.9 and item2 != 0 and sorted_code[(rowloop.index)-1] not in exclude_code and sorted_code[(loop.index)-1] not in exclude_code %}
        {{ '%.2f' | format(item2) }}
        {% endif %}
        {% if loop.index == rowloop.index %}
        x
        {% endif %}
        </td>
        {% endfor %}</tr>
    {%- endfor %}
    </tbody>
  </table>

  </body>
</html>
''')

print tmpl.render(
    sorted_code = sorted_code,
    matrix = new_matrix,
    exclude_code = exclude_code,
)

