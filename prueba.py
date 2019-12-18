from lxml import etree
from netconf import util


xml = etree.fromstring("<data xmlns:a='cucu'><datum><name>t</name></datum></data>")
xml_ = etree.ElementTree(xml)
nsmap = xml.nsmap

print(nsmap)


filt = xml_.xpath("/data/datum[name='t']", namespaces=nsmap)

for f in filt:
    print(etree.tostring(f, pretty_print=True))