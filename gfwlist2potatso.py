# coding=utf-8

from __future__ import print_function

import re
import os
import json
import datetime
import base64
import argparse
import codecs
import StringIO
import sys
import requests
from urlparse import urlparse


GFWLIST_URL = 'https://raw.githubusercontent.com/gfwlist/gfwlist/master/gfwlist.txt'
IP_REGEX = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b')

EXTRA_DOMAIN = [
    'sf.net',
    'hkheadline.com',
    'xda-developers.com',
    'wordpress.com'
]

EXTRA_DOMAIN_KEYWORD = [
    'google',
    'facebook',
    'youtube',
    'twitter'
]

# toml不能有序输出 拼字符串吧
OUTPUT = u'''name = "gfwlist to potatso ruleset"
description = "generate @ %(dt_detail_second)s"
website = "https://github.com/fpfeng/g2w.online"

[RULESET.gfwlist_proxy]
name = "gfwlist %(dt_short_date)s"
rules = %(rule_proxy)s

[RULESET.gfwlist_direct]
name = "gfwlist 直连白名单 %(dt_short_date)s"
rules = %(rule_direct)s
'''

def fetch_gfwlist(local_path):
    if local_path:
        try:
            with codecs.open(abspath(local_path), 'r', 'utf-8') as fp:
                content = StringIO.StringIO(base64.decodestring(fp.read()))
        except:
            error('base64 decode fail.', exit=True)
    else:
        try:
            resp = requests.get(GFWLIST_URL, timeout=10)
            content = StringIO.StringIO(resp.content.decode('base64'))
        except:
            error('fetch gfwlist fail.', exit=True)
    
    for l in content.readlines():
        line = l.rstrip()
        # 过滤：正则 注释 没有句号的关键字词 星号匹配url
        if line \
            and line[0] not in ['/', '!', '['] \
            and '.' in line \
            and '*' not in line \
            and not any(k in line for k in EXTRA_DOMAIN_KEYWORD):
            yield line

def extract_domain(line):
    # 暴力整个域名匹配 如果走代理 会有误伤 费点流量
    domain = urlparse(line).netloc
    if not domain: # 有些http开头
        slash_index = line.find('/') # 子目录被墙 
        if slash_index != -1:
            domain = line[:slash_index]
        else:
            domain = line

    return domain


def check_exist_then_add(line, rule):
    if line not in rule:
        rule.append(line)

def generate(gfwlist):
    direct = []
    proxy = []
    
    for line in gfwlist:
        if IP_REGEX.findall(line): # 抛弃ip
            continue
        elif line.startswith('@@'): # 直连
            line = line.replace('@@||', '').replace('@@|', '')
            line = 'DOMAIN-SUFFIX, {}, DIRECT'.format(extract_domain(line))
            check_exist_then_add(line, direct)
        elif line[0] in ['|', '.']: # 整个域名
            line = line.replace('||', '').replace('|', '')
            if line[0] == '.':
                line = line[1:]
            line = 'DOMAIN-SUFFIX, {}, PROXY'.format(extract_domain(line))
            check_exist_then_add(line, proxy)
        else:
            line = 'DOMAIN-SUFFIX, {}, PROXY'.format(extract_domain(line))
            check_exist_then_add(line, proxy)


    for d in EXTRA_DOMAIN:
        line = 'DOMAIN-SUFFIX, {}, PROXY'.format(extract_domain(d))
        check_exist_then_add(line, proxy)
    
    for k in EXTRA_DOMAIN_KEYWORD:
        proxy.append('DOMAIN-MATCH, {}, PROXY'.format(k))

    rules = {
        'proxy': proxy,
        'direct': direct,
    }

    return rules

def abspath(path):
    if not path:
        return path
    if path.startswith('~'):
        path = os.path.expanduser(path)
    return os.path.abspath(path)


def error(*args, **kwargs):
    print(*args, file=sys.stderr)
    if kwargs.get('exit', False):
        sys.exit(1)


def get_args():
    parser = argparse.ArgumentParser(
        description='transfer gfwlist to potatso ruleset')
    parser.add_argument('-l', '--local', type=str)
    parser.add_argument('-o', '--output', type=str, required=True)
    args = parser.parse_args()
    local_path = args.local
    output_path = args.output
    return local_path, output_path


def main():
    local_path, output_path = get_args()
    rules = generate(fetch_gfwlist(local_path))
    output = OUTPUT % {
        'dt_detail_second': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'dt_short_date': datetime.datetime.now().strftime('%Y-%m-%d'),
        'rule_proxy': json.dumps(rules['proxy'], indent=4),
        'rule_direct': json.dumps(rules['direct'], indent=4),
    }
    
    if output_path == '-':
        return sys.stdout.write(output)
    else:
        try:
            with codecs.open(abspath(output_path), 'w', 'utf-8') as fp:
                fp.write(output)
        except Exception as e:
            error('write output file fail: %s' % str(e), exit=True)

if __name__ == '__main__':
    main()
