#!/usr/bin/env python3

import io
import tarfile
import zipfile
import re
import os.path
import urllib.request
from typing import Tuple, NamedTuple, Iterable
import bs4
from html2xhtml import html2xhtml

Metadata = NamedTuple("Metadata", [
    ("title", str),
    ("author", str),
])

Chapter = NamedTuple("Chapter", [
    ("title", str),
    ("number", int),
    ("outname", str),
    ("xhtml", str),
])

Book = NamedTuple("Book", [
    ("metadata", Metadata),
    ("chapters", Iterable[Chapter]),
])

def metadata_from_html(html: bytes) -> Metadata:
    body = bs4.BeautifulSoup(html, "lxml").html.body
    return Metadata(
        title=str(body.find_all("h1")[0].text),
        author=str(body.h2.text),
    )

def chapter_from_html(filename: str, xhtml: str) -> Chapter:
    title = str(bs4.BeautifulSoup(xhtml, "lxml").html.body.find_all("h1")[-1].text)
    outname = os.path.basename(filename)
    match = re.search(r"([0-9]+)\.html$", outname)
    if match is None:
        raise ValueError
    number = int(match.group(1))
    return Chapter(title, number, outname, xhtml)

def book_from_tar_archive(archive: bytes) -> Book:
    html_toc_filename = "zshguide.html"
    metadata = None
    chapters = []
    tar = tarfile.open(fileobj=io.BytesIO(archive))
    for tarinfo in tar:
        if not tarinfo.isreg():
            continue
        if os.path.basename(tarinfo.name) == html_toc_filename:
            metadata = metadata_from_html(
                tar.extractfile(tarinfo).read() # type: ignore
            )
            continue
        if re.search(r"zshguide([0-9]{2})\.html$", tarinfo.name):
            chapters.append(chapter_from_html(
                tarinfo.name,
                remove_html_toc_references(
                    html2xhtml(
                        tar.extractfile(tarinfo).read() # type: ignore
                    ),
                    html_toc_filename
                )
            ))
            continue
    tar.close()
    if metadata is None:
        raise ValueError
    chapters.sort(key=lambda x: x.number)
    return Book(metadata, tuple(chapters))

def remove_html_toc_references(html: str, toc_filename: str) -> str:
    soup = bs4.BeautifulSoup(html, 'lxml')
    toc_links = soup.find_all("a", {"href": toc_filename})
    for toc_link in toc_links:
        if toc_link.parent.name == "li":
            toc_link.parent.decompose()
        else:
            raise ValueError
    return str(soup)

def create_ncx(book: Book, uuid: str) -> Tuple[str, str]:
    soup = bs4.BeautifulSoup('', 'lxml-xml')
    doctype = bs4.Doctype.for_name_and_ids(
        'ncx',
        '-//NISO//DTD ncx 2005-1//EN',
        'http://www.daisy.org/z3986/2005/ncx-2005-1.dtd'
    )
    soup.append(doctype)
    ncx = soup.new_tag(
        'ncx',
        xmlns="http://www.daisy.org/z3986/2005/ncx/",
        version="2005-1"
    )
    soup.append(ncx)

    head = soup.new_tag('head')
    dtb_meta = [
        ("uid", "urn:uuid:" + uuid),
        ("depth", "1"),
        ("totalPageCount", "0"),
        ("maxPageNumber", "0"),
    ]
    for meta_name, meta_content in dtb_meta:
        meta = soup.new_tag('meta')
        meta['name'] = 'dtb:' + meta_name
        meta['content'] = meta_content
        head.append(meta)
    ncx.append(head)

    title = soup.new_tag('docTitle')
    text = soup.new_tag('text')
    text.append(book.metadata.title)
    title.append(text)
    ncx.append(title)

    nav_number = 1
    nav_map = soup.new_tag('navMap')
    for chapter in book.chapters:
        nav_point = soup.new_tag('navPoint')
        nav_point['id'] = "navpoint-%d" % nav_number
        nav_point['playOrder'] = nav_number
        nav_number += 1
        nav_map.append(nav_point)
        nav_label = soup.new_tag('navLabel')
        nav_text = soup.new_tag('text')
        nav_text.append(chapter.title)
        nav_label.append(nav_text)
        nav_point.append(nav_label)
        nav_point.append(soup.new_tag('content', src=chapter.outname))
        chapter_soup = bs4.BeautifulSoup(chapter.xhtml, 'lxml')
        titles = chapter_soup.find_all('h2')
        for title in titles:
            title_link_id = title.previous_sibling.a['id']
            sub_nav_point = soup.new_tag('navPoint')
            sub_nav_point['id'] = "navpoint-%d" % nav_number
            sub_nav_point['playOrder'] = nav_number
            nav_number += 1
            sub_nav_label = soup.new_tag('navLabel')
            sub_nav_text = soup.new_tag('text')
            sub_nav_text.append(title.text)
            sub_nav_label.append(sub_nav_text)
            sub_nav_point.append(sub_nav_label)
            sub_nav_point.append(soup.new_tag('content', src=chapter.outname + '#' + title_link_id))
            nav_point.append(sub_nav_point)

    ncx.append(nav_map)
    return 'OEBPS/toc.ncx', str(soup)

def create_opf(book: Book, uuid: str) -> Tuple[str, str]:
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
    title.append(book.metadata.title)
    creator = soup.new_tag('dc:creator')
    creator.append(book.metadata.author)
    identifier = soup.new_tag('dc:identifier')
    identifier['id'] = "bookid"
    identifier.append(uuid)
    language = soup.new_tag('dc:language')
    language.append('en-US')
    for element in title, creator, identifier, language:
        metadata.append(element)

    manifest = soup.new_tag('manifest')
    spine = soup.new_tag('spine', toc="ncx")
    item_ncx_attrs = {
        'id': "ncx",
        'href': "toc.ncx",
        'media-type': "application/x-dtbncx+xml",
    }
    item_ncx = soup.new_tag('item', **item_ncx_attrs)
    manifest.append(item_ncx)
    for chapter in book.chapters:
        file_id = os.path.splitext(chapter.outname)[0]
        item_attrs = {
            'id': file_id,
            'href': chapter.outname,
            'media-type': "application/xhtml+xml",
        }
        item = soup.new_tag('item', **item_attrs)
        manifest.append(item)
        ref_attrs = {
            'idref': file_id,
        }
        ref = soup.new_tag('itemref', **ref_attrs)
        spine.append(ref)

    for element in metadata, manifest, spine:
        package.append(element)
    return 'OEBPS/content.opf', str(soup)

def create_mime() -> Tuple[str, str]:
    return 'mimetype', 'application/epub+zip'

def create_container() -> Tuple[str, str]:
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
    return 'META-INF/container.xml', str(soup)

def main() -> None:
    guide_url = 'http://zsh.sourceforge.net/Guide/'
    tarball_url = 'http://zsh.sourceforge.net/Guide/zshguide_html.tar.gz'
    archive = urllib.request.urlopen(tarball_url).read()
    book = book_from_tar_archive(archive)
    epub_contents = [('OEBPS/' + c.outname, c.xhtml) for c in book.chapters]
    epub_contents.append(create_ncx(book, guide_url))
    epub_contents.append(create_opf(book, guide_url))
    # the first file in the archive must be the mimetype file
    epub_contents.insert(0, create_mime())
    epub_contents.append(create_container())

    epub = zipfile.ZipFile('zsh-guide.epub', 'w')
    for filename, contents in epub_contents:
        compress = filename != 'mimetype'
        compression_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
        # the mimetype file must not be compressed; this allows non-ZIP
        # utilities to discover the mimetype by reading the raw bytes
        # from the EPUB file
        epub.writestr(filename, contents.encode('utf-8'), compression_type)

if __name__ == '__main__':
    main()
