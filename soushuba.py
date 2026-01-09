# -*- coding: utf-8 -*-
"""
实现搜书吧论坛登入和发布空间动态
"""
import os
import re
import sys
from copy import copy

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import time
import logging
import urllib3
import random

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

ch = logging.StreamHandler(stream=sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

def get_refresh_url(url: str):
    try:
        response = requests.get(url)
        if response.status_code != 403:
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        meta_tags = soup.find_all('meta', {'http-equiv': 'refresh'})

        if meta_tags:
            content = meta_tags[0].get('content', '')
            if 'url=' in content:
                redirect_url = content.split('url=')[1].strip()
                logger.info(f"Redirecting to: {redirect_url}")
                return redirect_url
        else:
            logger.error("No meta refresh tag found.")
            return None
    except Exception as e:
        logger.exception(f'An unexpected error occurred: {e}')
        return None

def get_url(url: str):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'html.parser')
    
    links = soup.find_all('a', href=True)
    for link in links:
        if link.text == "搜书吧":
            return link['href']
    return None

class SouShuBaClient:

    def __init__(self, hostname: str, username: str, password: str, questionid: str = '0', answer: str = None,
                 proxies: dict | None = None):
        self.session: requests.Session = requests.Session()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.questionid = questionid
        self.answer = answer
        self._common_headers = {
            "Host": f"{ hostname }",
            "Connection": "keep-alive",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,cn;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.proxies = proxies

    def login_form_hash(self):
        rst = self.session.get(f'https://{self.hostname}/member.php?mod=logging&action=login', verify=False).text
        loginhash = re.search(r'<div id="main_messaqge_(.+?)">', rst).group(1)
        formhash = re.search(r'<input type="hidden" name="formhash" value="(.+?)" />', rst).group(1)
        return loginhash, formhash

    def login(self):
        """Login with username and password"""
        loginhash, formhash = self.login_form_hash()
        login_url = f'https://{self.hostname}/member.php?mod=logging&action=login&loginsubmit=yes' \
                    f'&handlekey=register&loginhash={loginhash}&inajax=1'


        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f'https://{self.hostname}/'
        payload = {
            'formhash': formhash,
            'referer': f'https://{self.hostname}/',
            'username': self.username,
            'password': self.password,
            'questionid': self.questionid,
            'answer': self.answer
        }

        resp = self.session.post(login_url, proxies=self.proxies, data=payload, headers=headers, verify=False)
        if resp.status_code == 200:
            logger.info(f'Welcome {self.username}!')
        else:
            raise ValueError('Verify Failed! Check your username and password!')

    def credit(self):
        credit_url = f"https://{self.hostname}/home.php?mod=spacecp&ac=credit&showcredit=1&inajax=1&ajaxtarget=extcreditmenu_menu"
        credit_rst = self.session.get(credit_url, verify=False).text

        # 解析 XML，提取 CDATA
        root = ET.fromstring(str(credit_rst))
        cdata_content = root.text

        # 使用 BeautifulSoup 解析 CDATA 内容
        cdata_soup = BeautifulSoup(cdata_content, features="lxml")
        hcredit_2 = cdata_soup.find("span", id="hcredit_2").string

        return hcredit_2

    def space_form_hash(self):
        rst = self.session.get(f'https://{self.hostname}/home.php', verify=False).text
        formhash = re.search(r'<input type="hidden" name="formhash" value="(.+?)" />', rst).group(1)
        return formhash

    def _random_modify_message(self, message: str) -> str:
        """对消息进行随机修改，增加合理的变化"""
        # 30%概率保持原样
        if random.random() < 0.3:
            return message
        # 收集可能的修改方式
        modifications = []
        # 添加表情符号（30%概率）
        if random.random() < 0.3:
            emoji_sets = [
                ["😊", "👍", "🌟"],  # 基础正面表情
                ["✨", "🌸", "☀️"],  # 自然主题
                ["💪", "🔥", "⭐️"],  # 鼓励主题
                ["😄", "😌", "😇"],  # 表情主题
            ]
            emoji = random.choice(random.choice(emoji_sets))
            modifications.append(lambda msg, e=emoji: f"{msg} {e}")
        # 微调标点符号（25%概率）
        if random.random() < 0.25:
            punctuation_mods = [
                lambda msg: msg.replace("。", "~"),
                lambda msg: msg.replace("。", "..."),
                lambda msg: msg.replace("，", ", "),
                lambda msg: msg[:-1] + "！" if msg.endswith("。") else msg,
            ]
            modifications.append(random.choice(punctuation_mods))
        # 简单后缀（20%概率）
        if random.random() < 0.2:
            suffixes = [
                "继续努力！",
                "加油~",
                "明天会更好！",
                "一起加油！",
                "坚持就是胜利！",
            ]
            suffix = random.choice(suffixes)
            modifications.append(lambda msg, s=suffix: f"{msg} {s}")
        # 微调开头词语（10%概率）
        if random.random() < 0.1 and len(message) > 4:
            adjustments = [
                lambda msg: msg.replace("今天", "今日").replace("今天", "今日"),
                lambda msg: msg.replace("保持", "坚持").replace("保持", "坚持"),
                lambda msg: msg.replace("简单", "平淡").replace("简单", "平淡"),
                lambda msg: "嗯，" + msg if not msg.startswith("嗯") else msg,
            ]
            modifications.append(random.choice(adjustments))
        # 添加简单前缀（5%概率）
        if random.random() < 0.05:
            prefixes = [
                "今日心情：",
                "随手记录：",
                "日常随笔：",
            ]
            prefix = random.choice(prefixes)
            modifications.append(lambda msg, p=prefix: f"{p}{msg}")
        # 应用所有选中的修改（按顺序）
        final_message = message
        if modifications:
            # 随机打乱修改顺序以获得更多变化
            random.shuffle(modifications)
            # 限制最多应用3种修改，避免过度修改
            max_mods = min(3, len(modifications))
            selected_mods = random.sample(modifications, random.randint(1, max_mods))
            for mod_func in selected_mods:
                final_message = mod_func(final_message)
        # 确保消息长度适中，不超过50个字符（中文字符算1个）
        if len(final_message) > 50:
            # 如果太长，保留主要部分
            if "。" in final_message:
                final_message = final_message.split("。")[0] + "。"
            else:
                final_message = final_message[:45] + "..." if len(final_message) > 45 else final_message
        # 确保消息以合适的标点结尾
        if not final_message[-1] in "。！～~…":
            final_message += "。"
        # 处理可能的重复标点
        final_message = re.sub(r'([。！～~…])\1+', r'\1', final_message)
        return final_message

    def space(self):
        formhash = self.space_form_hash()
        space_url = f"https://{self.hostname}/home.php?mod=spacecp&ac=doing&handlekey=doing&inajax=1"

        # 10条通用日常短语
        daily_messages = [
            "今天天气不错，心情也很好。",
            "记录下今日的小确幸。",
            "保持好心态，享受当下。",
            "简单生活，快乐每一天。",
            "感谢生活中的点滴美好。",
            "放空自己，享受宁静时刻。",
            "平凡的一天，简单而充实。",
            "珍惜当下，感恩拥有。",
            "保持积极，继续前行。",
            "每一天都是新的开始。"
        ]

        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f'https://{self.hostname}/home.php'

        # 决定发布次数：80%概率发1次，20%概率发2次
        post_count = 1 if random.random() < 0.8 else 2
        logger.info(f'计划发布 {post_count} 条动态')
        # 已使用的消息，避免重复使用同一原始消息
        used_messages = []

        for x in range(post_count):
            
            # 从没用过的消息中选择
            available_messages = [msg for msg in daily_messages if msg not in used_messages]
            if not available_messages:
                available_messages = daily_messages  # 如果都用过了，重置               
            # 随机选择一条消息
            base_message = random.choice(available_messages)
            used_messages.append(base_message) 
            # 对消息进行随机修改
            final_message = self._random_modify_message(base_message)
            
            payload = {
                "message": final_message.encode("GBK"),
                "addsubmit": "true",
                "spacenote": "true",
                "referer": "home.php",
                "formhash": formhash
            }
            resp = self.session.post(space_url, proxies=self.proxies, data=payload, headers=headers, verify=False)
            if re.search("操作成功", resp.text):
                logger.info(f'{self.username} post {x + 1}nd successfully!')
                # 如果不是最后一次发布，等待随机间隔（100-120秒）
                if x < post_count - 1:
                    interval = random.uniform(100, 120)
                    logger.info(f'等待 {interval:.1f} 秒后发布下一条...')
                    time.sleep(interval)
            else:
                logger.warning(f'{self.username} post {x + 1}nd failed!')


if __name__ == '__main__':
    try:
        redirect_url = get_refresh_url('http://' + os.environ.get('SOUSHUBA_HOSTNAME', 'www.soushu2035.com'))
        time.sleep(2)
        redirect_url2 = get_refresh_url(redirect_url)
        url = get_url(redirect_url2)
        logger.info(f'{url}')
        client = SouShuBaClient(urlparse(url).hostname,
                                os.environ.get('SOUSHUBA_USERNAME', "USERNAME"),
                                os.environ.get('SOUSHUBA_PASSWORD', "PASSWORD"))
        client.login()
        client.space()
        credit = client.credit()
        logger.info(f'{client.username} have {credit} coins!')
    except Exception as e:
        logger.error(e)
        sys.exit(1)
