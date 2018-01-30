#!/usr/bin/env python3
from datetime import datetime
from pathlib import PurePath, Path
from itertools import chain
from subprocess import CalledProcessError

from lettersmith.argparser import lettersmith_argparser, read_config
from lettersmith import path as pathtools
from lettersmith import docs as Docs
from lettersmith import doc as Doc
from lettersmith import markdowntools
from lettersmith import wikilink
from lettersmith import absolutize
from lettersmith.permalink import map_permalink
from lettersmith import templatetools
from lettersmith import paging
from lettersmith import taxonomy
from lettersmith import jinjatools
from lettersmith import cachetools
from lettersmith.data import load_data_files
from lettersmith.file import copy, copy_all



def main():
    parser = lettersmith_argparser(
        description="""Generates a blog-aware site with Lettersmith""")
    args = parser.parse_args()
    config = read_config(args.config)
    input_path = config["input_path"]
    output_path = config["output_path"]
    cache_path = config["cache_path"]
    theme_path = config["theme_path"]
    base_url = config["base_url"]

    data = load_data_files(config["data_path"])

    md_paths = tuple(Path(input_path).glob("**/*.md"))
    docs = Docs.load(md_paths, relative_to=input_path)
    docs = docs if config["build_drafts"] else Docs.remove_drafts(docs)

    docs = (Doc.decorate_smart_items(doc) for doc in docs)
    docs = templatetools.map_templates(docs)
    docs = (wikilink.uplift_wikilinks(doc) for doc in docs)
    docs = map_permalink(docs, config["permalink_templates"])

    doc_cache_path = PurePath(cache_path, "docs")
    cachetools.write_cache(doc_cache_path, docs)

    stub_docs = cachetools.read_cache(doc_cache_path)
    stub_docs = tuple(Doc.rm_content(doc) for doc in stub_docs)
    wikilink_index = wikilink.index_wikilinks(stub_docs, base=base_url)
    backlink_index = wikilink.index_backlinks(stub_docs)
    index = Docs.reduce_index(stub_docs)
    taxonomy_index = taxonomy.index_by_taxonomy(stub_docs, config["taxonomies"])
    paging_docs = paging.gen_paging(stub_docs, **config["paging"])

    docs = cachetools.read_cache(doc_cache_path)
    docs = wikilink.map_wikilinks(docs,
        wikilink_index=wikilink_index, base=base_url)
    docs = markdowntools.map_markdown(docs)
    docs = absolutize.map_absolutize(docs, base=base_url)
    docs = (Doc.decorate_summary(doc) for doc in docs)

    docs = chain(docs, paging_docs)

    # Set up template globals
    context = {
        "index": index,
        "taxonomy_index": taxonomy_index,
        "backlink_index": backlink_index,
        "site": config["site"],
        "data": data,
        "base_url": base_url,
        "now": datetime.now()
    }

    docs = jinjatools.map_jinja(docs, context=context, theme_path=theme_path)

    # Copy static files from project dir (if any)
    try:
        copy_all(config["static_paths"], output_path)
    except CalledProcessError:
        pass

    # Copy static files from theme (if any)
    try:
        copy(PurePath(theme_path, "static"), output_path)
    except CalledProcessError:
        pass

    stats = Docs.write(docs, output_path=output_path)

    print('Done! Generated {sum} files in "{output_path}"'.format(
        output_path=output_path,
        sum=stats["written"]
    ))


if __name__ == "__main__":
    main()