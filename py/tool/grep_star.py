import os
import sys
file=sys.argv[1]
name=sys.argv[2]

i = 0
for line in open(file): 
    i += 1
    if line.startswith(name):
        print(i)
        sys.exit(0)

