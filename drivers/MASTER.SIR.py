"""
Use XML template to generate control file for generating
a tree under an SI model with MASTER 2.0 (BEAST).
"""
import jinja2
import os
import sys
from Bio import Phylo
from random import sample
import subprocess
import time
from datetime import datetime
from settings import jarfile  # absolute path to MASTER-2.0 jarfile

# TODO: allow user to set time limit and step for MASTER

time_limit = 60  # seconds - when do we reduce the number of tips
time_step = 10 # seconds - how often we check the file for completion


FNULL = open(os.devnull, 'w')

try:
    infile = sys.argv[1]
    tipfile = sys.argv[2]
    outfile = sys.argv[3]
except:
    print 'Usage: python MASTER.SIR.py [input CSV] [tip labels CSV] [output NWK]'
    sys.exit(1)

# get parent process ID from filename
try:
    pid = int(infile.split('.')[0].split('_')[-1])
    tmpfile = '/tmp/MASTER.SIR.%d.xml' % pid
except:
    tmpfile = '/tmp/MASTER.SIR.xml'

jenv = jinja2.Environment(
    block_start_string='{%',
    block_end_string='%}',
    variable_start_string='{{',
    variable_end_string='}}',
    loader=jinja2.FileSystemLoader(os.getcwd())
)

template = jenv.from_string(source=
"""
<beast version='2.0' namespace='master
                                :master.model
                                :master.conditions
                                :master.outputs
                                :master.postprocessors'>
    <run spec='InheritanceEnsemble'
         nTraj='{{ nreps|int }}'
         samplePopulationSizes="true"
         verbosity="0"
         simulationTime="{{ 1.1*t_end }}">

        <model spec='Model' id='model'>
            <population spec='Population' id='S' populationName='S'/>
            <population spec='Population' id='I' populationName='I'/>
            <population spec='Population' id='R' populationName='R'/>
            <population spec='Population' id='I_sample' populationName='I_sample'/>

            <reaction spec='Reaction' reactionName="Infection" rate="{{ beta }}">
                S + I -> 2I
            </reaction>
            <reaction spec='Reaction' reactionName="Recovery" rate="{{ gamma }}">
                I -> R
            </reaction>
            <reaction spec='Reaction' reactionName="Sampling" rate="{{ phi }}">
                I -> I_sample
            </reaction>
        </model>

        <initialState spec='InitState'>
            <populationSize spec='PopulationSize' population='@S' size='{{ N - 1 }}'/>
            <lineageSeed spec='Individual' population='@I'/>
        </initialState>

        <inheritancePostProcessor spec="LineageFilter" reactionName="Sampling"/>
        <postSimCondition spec="LeafCountPostSimCondition" nLeaves="{{ ntips }}" exact="false"/>

        <output spec='NewickOutput' fileName='{{ outfile }}'/>
    </run>
</beast>
""")

# default parameter values
context = {
    'beta': 0.001,  # transmission rate
    'gamma': 0.3,  # mortality rate
    'N': 1000,      # total population size
    't_end': 30,    # length of simulation
    'phi': 0.15,    # sampling rate
    'ntips': 100,    # number of tips in tree
    'nreps': 10,     # number of trees to generate
    'outfile': outfile
}


# read parameter settings from input CSV
handle = open(infile, 'rU')
for line in handle:
    key, value = line.strip('\n').split(',')
    context.update({key: float(value)})
handle.close()

# FIXME: MASTER tends to generate larger trees than requested
# FIXME: setting post filter to "exact" is extremely inefficient
# infer number of tips from tip label CSV
handle = open(tipfile, 'rU')
context['ntips'] = len(handle.readlines())
handle.close()

# reduce requested number of tips for more efficient simulation
context['ntips'] = int(round(context['ntips'] * 1.0))

# populate template from context
handle = open(tmpfile, 'w')
handle.write(template.render(context))
handle.close()

# remove previous Newick output if it exists
if os.path.exists(outfile):
    os.remove(outfile)

print '[%s] calling master2' % datetime.now().isoformat()

# call MASTER

print '[%s] calling master2' % datetime.now().isoformat()

#os.system('master2 %s > /dev/null' % tmpfile)
p = subprocess.Popen(['java', '-Xms1024m', '-Xmx2048m', '-jar', jarfile, tmpfile],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# check if outfile has expected number of lines
elapsed = 0
ntips = context['ntips']  # remember original number
while 1:
    time.sleep(time_step)
    handle = open(outfile, 'rU')
    lines = handle.readlines()
    if len(lines) == context['nreps']:
        # generated the requested number of replicates
        break

    elapsed += time_step
    if elapsed > time_limit:
        # taking too long - reduce requested number of tips
        p.kill()

        # reduce requested number of tips by 20%
        context['ntips'] = int(round(context['ntips'] * 0.5))
        if context['ntips'] < 30:
            print 'ERROR: ntips cannot be less than 2'
            sys.exit(1)

        # update template
        handle = open(tmpfile, 'w')
        handle.write(template.render(context))
        handle.close()

        p = subprocess.Popen(['java', '-Xms512m', '-Xmx2048m', '-jar', jarfile, tmpfile],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        elapsed = 0  # reset timer

p.kill()


# sample tips to enforce size of tree
trees = Phylo.parse(outfile, 'newick')
trees2 = []
while True:
    try:
        tree = trees.next()
    except StopIteration:
        break
    except NewickError:
        continue
        
    tips = tree.get_terminals()
    try:
        tips2 = sample(tips, ntips)
    except ValueError:
        # sample size exceeds population
        trees2.append(tree)
        continue

    # dict object provides faster lookup
    keep = dict([(tip, 0) for tip in tips2])

    for tip in tips:
        tip.name = str(tip.confidence)
        if tip in keep:
            continue
        _ = tree.prune(tip)
    trees2.append(tree)

print '[%s] pruned trees' % datetime.now().isoformat()

Phylo.write(trees2, outfile, 'newick')
