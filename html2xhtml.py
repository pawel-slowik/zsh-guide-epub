#!/usr/bin/env python3
from typing import Union, Any
import bs4

DOCTYPES = {
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

def html2xhtml(html: Union[str, bytes], version: str = '1.1') -> str:
    soup = bs4.BeautifulSoup(html, "lxml")
    set_doctype(soup, version)
    set_xml_namespace(soup)
    set_charset(soup)
    remove_empty_paragraphs(soup)
    if version == '1.1':
        convert_name_to_id(soup)
    wrap_body(soup)
    return str(soup)

def set_doctype(soup: bs4.BeautifulSoup, version: str) -> None:
    if version not in DOCTYPES:
        raise ValueError('unsupported version: %s' % version)
    new_doctype = bs4.Doctype.for_name_and_ids(*DOCTYPES[version])
    for item in soup.contents:
        if isinstance(item, bs4.Doctype):
            item.replaceWith('')
    soup.insert(0, new_doctype)

def set_xml_namespace(soup: bs4.BeautifulSoup) -> None:
    soup.html['xmlns'] = 'http://www.w3.org/1999/xhtml'

def set_charset(soup: bs4.BeautifulSoup) -> None:

    def element_is_meta_charset(element: Any) -> bool:
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

def remove_empty_paragraphs(soup: bs4.BeautifulSoup) -> None:

    def is_empty(tag: Any) -> bool:
        for child in tag.children:
            if isinstance(child, bs4.element.Tag):
                return False
            if isinstance(child, bs4.element.NavigableString):
                if child.strip() != '':
                    return False
                continue
            return False
        return True

    for element in soup.find_all('p'):
        if is_empty(element):
            element.decompose()

def convert_name_to_id(soup: bs4.BeautifulSoup) -> None:
    for anchor in soup.html.find_all('a'):
        if anchor.has_attr('name'):
            anchor['id'] = anchor['name']
            del anchor['name']

def wrap_body(soup: bs4.BeautifulSoup) -> None:
    wrapper = soup.new_tag('div')
    saved = list(soup.body.children)
    soup.body.clear()
    soup.body.append(wrapper)
    for saved_element in saved:
        wrapper.append(saved_element)

def main() -> None:
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
        choices=list(DOCTYPES.keys()),
        default='1.1',
        help='XHTML version'
    )
    args = parser.parse_args()
    html = open(args.input_file, 'r').read()
    xhtml = html2xhtml(html, args.version)
    open(args.output_file, 'wb').write(xhtml.encode('utf-8'))

if __name__ == "__main__":
    main()
