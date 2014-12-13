"""
Populate BEAST2 XML template with new sequence data from FASTA
"""

from xml.etree.ElementTree import ElementTree as Tree
from xml.etree.ElementTree import Element as Node
from seqUtils import convert_fasta
import sys
import os

try:
    template = sys.argv[1]
    infile = sys.argv[2]
except:
    print 'Usage: python populate_beast2_xml.py [template XML] [input FASTA]'
    sys.exit()
    
handle = open(infile, 'rU')
fasta = convert_fasta(handle)
handle.close()

# extract tip dates

template = Tree()
root = template.parse(template)

data = template.findall('data')[0]
data._children = []  # reset data block

tipdates = ''
for h, s in fasta:
    tipdate = h.split('_')[-1]
    tipdates += '%s = %s, ' % (h, tipdate)
    seq = Node('sequence', {'totalcount': 4, 'id': 'seq_seq_'+h, 'value': s, 'taxon': h})
    data._children.append(seq)


# replace tip date information
traits = template.find('trait')
traits.set('value', tipdates.strip(','))

