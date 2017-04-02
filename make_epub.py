#!/usr/bin/env python2.7
from __future__ import print_function
import StringIO
import tarfile
import zipfile
import re
import os.path
import bs4
from html2xhtml import html2xhtml

def get_archive_xhtml(archive):
	tar = tarfile.open(fileobj = StringIO.StringIO(archive))
	name_xhtml_map = {}
	for tarinfo in tar:
		if not tarinfo.isreg():
			continue
		if not re.search(r'zshguide([0-9]{2}){0,1}\.html$', tarinfo.name):
			continue
		xhtml = html2xhtml(tar.extractfile(tarinfo).read())
		outname = os.path.basename(tarinfo.name)
		name_xhtml_map[outname] = xhtml
	tar.close()
	return name_xhtml_map

def create_ncx(titles_map, uuid):
	soup = bs4.BeautifulSoup('', 'lxml-xml')
	doctype = bs4.Doctype.for_name_and_ids(
		'ncx',
		'-//NISO//DTD ncx 2005-1//EN',
		'http://www.daisy.org/z3986/2005/ncx-2005-1.dtd'
	)
	soup.append(doctype)
	ncx = soup.new_tag('ncx', xmlns = "http://www.daisy.org/z3986/2005/ncx/", version = "2005-1")
	soup.append(ncx)

	head = soup.new_tag('head')
	dtb_meta = [
		("uid", "urn:uuid:" + uuid),
		("depth", "1"),
		("totalPageCount", "0"),
		("maxPageNumber", "0"),
	]
	for meta_name, meta_content in dtb_meta:
		e = soup.new_tag('meta')
		e['name'] = 'dtb:' + meta_name
		e['content'] = meta_content
		head.append(e)
	ncx.append(head)

	title = soup.new_tag('docTitle')
	text = soup.new_tag('text')
	text.append(titles_map[sorted(titles_map.keys())[0]][0])
	title.append(text)
	ncx.append(title)

	nav_map = soup.new_tag('navMap')
	n = 1
	for k in sorted(titles_map.keys()):
		nav_point = soup.new_tag('navPoint')
		nav_point['id'] = "navpoint-%d" % n
		nav_point['playOrder'] = n
		nav_map.append(nav_point)
		nav_label = soup.new_tag('navLabel')
		nav_text = soup.new_tag('text')
		nav_text.append(titles_map[k][-1])
		nav_label.append(nav_text)
		nav_point.append(nav_label)
		nav_point.append(soup.new_tag('content', src = k))
		n += 1
	ncx.append(nav_map)
	return unicode(soup)

def create_opf(titles_map, author, uuid):
	soup = bs4.BeautifulSoup('', 'lxml-xml')
	package_attrs = {
		'xmlns': "http://www.idpf.org/2007/opf",
		'xmlns:dc': "http://purl.org/dc/elements/1.1/",
		'unique-identifier': "bookid",
		'version': "2.0",
	}
	package = soup.new_tag('package', **package_attrs)
	soup.append(package)

	metadata = soup.new_tag('metadata')
	title = soup.new_tag('dc:title')
	title.append(titles_map[sorted(titles_map.keys())[0]][0])
	creator = soup.new_tag('dc:creator')
	creator.append(author)
	identifier = soup.new_tag('dc:identifier')
	identifier['id'] = "bookid"
	identifier.append(uuid)
	language = soup.new_tag('dc:language')
	language.append('en-US')
	for e in title, creator, identifier, language:
		metadata.append(e)

	manifest = soup.new_tag('manifest')
	spine = soup.new_tag('spine', toc = "ncx")
	item_ncx_attrs = {
		'id': "ncx",
		'href': "toc.ncx",
		'media-type': "application/x-dtbncx+xml",
	}
	item_ncx = soup.new_tag('item', **item_ncx_attrs)
	manifest.append(item_ncx)
	for k in sorted(titles_map.keys()):
		file_id = os.path.splitext(k)[0]
		item_attrs = {
			'id': file_id,
			'href': k,
			'media-type': "application/xhtml+xml",
		}
		item = soup.new_tag('item', **item_attrs)
		manifest.append(item)
		ref = soup.new_tag('itemref', idref = file_id)
		spine.append(ref)

	for e in metadata, manifest, spine:
		package.append(e)
	return unicode(soup)

def create_mime():
	return 'application/epub+zip'

def create_container():
	soup = bs4.BeautifulSoup('', 'lxml-xml')
	container_attrs = {
		'xmlns': "urn:oasis:names:tc:opendocument:xmlns:container",
		'version': "1.0",
	}
	container = soup.new_tag('container', **container_attrs)
	rootfiles = soup.new_tag('rootfiles')
	rootfile_attrs = {
		'full-path': "OEBPS/content.opf",
		'media-type': "application/oebps-package+xml",
	}
	rootfile = soup.new_tag('rootfile', **rootfile_attrs)
	rootfiles.append(rootfile)
	container.append(rootfiles)
	soup.append(container)
	return unicode(soup)

def get_author(contents_map):
	# TODO
	return 'Peter Stephenson'

def list_titles(xhtml):
	soup = bs4.BeautifulSoup(xhtml, 'lxml')
	return [unicode(h1.text) for h1 in soup.html.body.find_all('h1')]

def main():
	guide_url = 'http://zsh.sourceforge.net/Guide/'
	archive = open('zshguide_html.tar.gz', 'rb').read()
	contents_map = get_archive_xhtml(archive)
	titles_map = {outname: list_titles(xhtml) for (outname, xhtml) in contents_map.iteritems()}
	epub_contents = [(['OEBPS', outname], xhtml) for (outname, xhtml) in contents_map.iteritems()]
	epub_contents.append((['OEBPS', 'toc.ncx'], create_ncx(titles_map, guide_url)))
	epub_contents.append((['OEBPS', 'content.opf'], create_opf(titles_map, get_author(contents_map), guide_url)))
	epub_contents.append((['mimetype'], create_mime()))
	epub_contents.append((['META-INF', 'container.xml'], create_container()))

	epub = zipfile.ZipFile('zsh-guide.epub', 'w')
	for filename, contents in epub_contents:
		epub.writestr(os.path.join(*filename), contents.encode('utf-8'))

if __name__ == '__main__':
	main()
