import re
from jinja2 import Template

regex = re.compile(r' \[.*?\] (.*)')
class_regex = re.compile(r'\[(.*?)(, (.*))?\]')
f = open('pylint_reddit_report.parse', 'r')

# (.*?):(\d+): \[(.*?)\] (.*)
dict_class = {}
code_set  = set()
class_set = set()
#exclude_code = ['C0203', 'C0321', 'C0322', 'C0324', 'E0101', 'F0401', 'W0102', 'W0105', 'W0106', 'W0122', 'W0231', 'W0311', 'W0701', 'W0702', 'W0703']
exclude_code = []
# 'W0601' to check 

for i, line in enumerate(f.readlines()):
    try :
        line = line.rstrip()
        split = line.split(':')
        filename = split[0]
        nline = split[1]
        fin = split[2]
        m = re.match(regex, fin)
        inter_code = m.group(0)
        ma = re.match(class_regex, inter_code.strip())
        
        code = ma.group(1)
        classe = ma.group(3)
        if classe:
            #print classe
            if not classe.split('.')[-1].isupper():
            #if 1==1:
                classe = classe.split('.')[1]
                if not classe in dict_class:
                    dict_class[classe] = set()

                dict_class[classe].add(code)
                code_set.add(code)
                class_set.add(classe)
            else:
                classe = None
        message = m.group(1)
        
    except :
        pass

sorted_code = list(code_set)
sorted_code.sort()
#print sorted_code

sorted_class = list(class_set)
sorted_class.sort()
#print sorted_class

matrix = []

for code in sorted_code:
    temp = []
    for cl in sorted_class:
        if code in dict_class[cl]:
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



show_code = list(sorted_code)
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
    for k,v in dict_class.iteritems():
        if code in v:
            pc += 1
    pc = float(pc) / float(total_code)
    if pc > 0.9: 
    	    exclude_code.append(code)

i = 0
for line in new_matrix:
    if sum( [1 for v in line if v <= 0.9 and v != 0] ) == 0 :
        exclude_code.append(sorted_code[i])
    i+=1

print 'Excluded codes : ', exclude_code


for ec in set(exclude_code):
    try:
        show_code.remove(ec)
    except:
        pass


tmpl = Template(u'''\
<!DOCTYPE html>
<html>
  <head>
    <title>Resultats</title>
  </head>
  <body>

  <table border="1">
    <thead>
        <tr>
        <th>/</th>
        {%- for sc in show_code %}<th>{{ sc }}</th>{%- endfor %}
        </tr>
    </thead>
    <tbody>

    {%- for item in matrix %}

        {% set rowloop = loop %}
        

        {% if sorted_code[(rowloop.index)-1] not in exclude_code %}

        <tr><td><b>{{ sorted_code[(rowloop.index)-1] }}</b></td>
        {% for item2 in item %}

            {% if sorted_code[(loop.index)-1] not in exclude_code %}
                <td style="background-color: rgb({{ '%d' | format(255*item2)  }}, {{ '%d' | format(255 * (100- (item2*100)) / 100) }}, 0);">
                    
                    {% if item2 < 0.9 and item2 != 0 %}
                        {{ '%.2f' | format(item2) }}
                    {% endif %}
                    
                </td>
            {% endif %}
        {% endfor %}

        {% endif %}
    </tr>    
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
    show_code = show_code
)

