import sys
name=sys.argv[1]
if len(sys.argv) < 2:
  print("")
  sys.exit(1)
try:
	name_byte=name.encode("latin1").decode('unicode_escape').encode('latin1')
	name_decode=name_byte.decode('utf-8')
	print(name_decode.replace('/','_'))
except Exception as e:
	print("")
	sys.exit(2)
