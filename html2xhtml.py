#!/usr/bin/env python2.7
import bs4

doctypes = {
	'1.0': (
		'html',
		'-//W3C//DTD XHTML 1.0 Strict//EN',
		'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd',
	),
	'1.1': (
		'html',
		'-//W3C//DTD XHTML 1.1//EN',
		'http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd',
	),
}

def html2xhtml(html, version='1.1'):
	soup = bs4.BeautifulSoup(html, "lxml")
	set_doctype(soup, version)
	set_xml_namespace(soup)
	set_charset(soup)
	remove_empty_paragraphs(soup)
	if version == '1.1':
		convert_name_to_id(soup)
	wrap_body(soup)
	return unicode(soup)

def set_doctype(soup, version):
	if version not in doctypes:
		raise ValueError('unsupported version: %s' % version)
	new_doctype = bs4.Doctype.for_name_and_ids(*doctypes[version])
	for item in soup.contents:
		if isinstance(item, bs4.Doctype):
			item.replaceWith('')
	soup.insert(0, new_doctype)

def set_xml_namespace(soup):
	soup.html['xmlns'] = 'http://www.w3.org/1999/xhtml'

def set_charset(soup):

	def element_is_meta_charset(element):
		if element.name != 'meta':
			return False
		if element.has_attr('charset'):
			return True
		if element.has_attr('http-equiv'):
			if element['http-equiv'] == 'Content-Type':
				return True
		return False

	for meta in soup.html.head.find_all(element_is_meta_charset):
		meta.decompose()
	meta_attrs = {
		'http-equiv': 'Content-Type',
		'content': 'text/html; charset=utf-8',
	}
	soup.html.head.append(soup.new_tag('meta', **meta_attrs))

def remove_empty_paragraphs(soup):

	def is_empty(tag):
		for c in tag.children:
			if isinstance(c, bs4.element.Tag):
				return False
			if isinstance(c, bs4.element.NavigableString):
				if c.strip() != '':
					return False
				continue
			return False
		return True

	for e in soup.find_all('p'):
		if is_empty(e):
			e.decompose()

def convert_name_to_id(soup):
	for a in soup.html.find_all('a'):
		if a.has_attr('name'):
			a['id'] = a['name']
			del a['name']

def wrap_body(soup):
	wrapper = soup.new_tag('div')
	saved = list(soup.body.children)
	soup.body.clear()
	soup.body.append(wrapper)
	for s in saved:
		wrapper.append(s)

def main():
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument(
		'-i',
		dest='input_file',
		required=True,
		help='input file'
	)
	parser.add_argument(
		'-o',
		dest='output_file',
		required=True,
		help='output file'
	)
	parser.add_argument(
		'-x',
		dest='version',
		required=False,
		choices=doctypes.keys(),
		default='1.1',
		help='XHTML version'
	)
	args = parser.parse_args()
	html = open(args.input_file, 'r').read()
	xhtml = html2xhtml(html, args.version)
	open(args.output_file, 'wb').write(xhtml.encode('utf-8'))

if __name__ == "__main__":
	main()
