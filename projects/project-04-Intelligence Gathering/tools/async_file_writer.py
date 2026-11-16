# -*- coding: utf-8 -*-
# Copyright (c) 2025 relakkes@gmail.com
#
# This file is part of MediaCrawler project.
# Repository: https://github.com/NanmiCoder/MediaCrawler/blob/main/tools/async_file_writer.py
# GitHub: https://github.com/NanmiCoder
# Licensed under NON-COMMERCIAL LEARNING LICENSE 1.1
#
# 声明：本代码仅供学习和研究目的使用。使用者应遵守以下原则：
# 1. 不得用于任何商业用途。
# 2. 使用时应遵守目标平台的使用条款和robots.txt规则。
# 3. 不得进行大规模爬取或对平台造成运营干扰。
# 4. 应合理控制请求频率，避免给目标平台带来不必要的负担。
# 5. 不得用于任何非法或不当的用途。
#
# 详细许可条款请参阅项目根目录下的LICENSE文件。
# 使用本代码即表示您同意遵守上述原则和LICENSE中的所有条款。

import asyncio
import csv
import json
import os
import pathlib
import re
from typing import Dict, List
import aiofiles
import config
from pipeline.io_utils import atomic_write_text
from tools.kb_paths import LINKED_REPOSITORY_DIR, kb_namespace, kb_source_dir, safe_segment, source_category
from tools.utils import utils
from tools.words import AsyncWordCloudGenerator

class AsyncFileWriter:
    def __init__(self, platform: str, crawler_type: str):
        self.lock = asyncio.Lock()
        self.platform = platform
        self.crawler_type = crawler_type
        self.wordcloud_generator = AsyncWordCloudGenerator() if config.ENABLE_GET_WORDCLOUD else None

    def _get_file_path(self, file_type: str, item_type: str) -> str:
        base_path = str(kb_source_dir(self.platform, file_type))
        pathlib.Path(base_path).mkdir(parents=True, exist_ok=True)
        # Include the configured search terms so multiple runs are easy to tell
        # apart in the result browser. Keep the name Windows-safe and bounded.
        keyword_label = re.sub(r'[<>:"/\\|?*\r\n]+', '_', str(config.KEYWORDS or 'all')).strip(' ._')
        keyword_label = re.sub(r"_+", "_", keyword_label)[:80] or "all"
        file_name = f"{self.crawler_type}_{keyword_label}_{item_type}_{utils.get_current_date()}.{file_type}"
        return f"{base_path}/{file_name}"

    def _enrich(self, item: Dict) -> Dict:
        category = source_category(self.platform)
        record = dict(item)
        record.setdefault("record_type", {"papers": "paper", "repositories": "repository"}.get(category, "platform_content"))
        record.setdefault("kb_namespace", kb_namespace())
        return record

    async def write_to_csv(self, item: Dict, item_type: str):
        item = self._enrich(item)
        file_path = self._get_file_path('csv', item_type)
        async with self.lock:
            file_exists = os.path.exists(file_path)
            async with aiofiles.open(file_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=item.keys())
                if not file_exists or await f.tell() == 0:
                    await writer.writeheader()
                await writer.writerow(item)

    async def write_to_jsonl(self, item: Dict, item_type: str):
        item = self._enrich(item)
        file_path = self._get_file_path('jsonl', item_type)
        async with self.lock:
            async with aiofiles.open(file_path, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(item, ensure_ascii=False) + '\n')

    async def write_single_item_to_json(self, item: Dict, item_type: str):
        item = self._enrich(item)
        file_path = self._get_file_path('json', item_type)
        async with self.lock:
            existing_data = []
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    try:
                        content = await f.read()
                        if content:
                            existing_data = json.loads(content)
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
                    except json.JSONDecodeError:
                        existing_data = []

            existing_data.append(item)

            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(existing_data, ensure_ascii=False, indent=4))

    async def write_linked_paper(self, paper_id: str, payload: Dict) -> None:
        """Store a paper's linked open-source repositories next to the paper files."""
        path = kb_source_dir(self.platform, LINKED_REPOSITORY_DIR) / f"{safe_segment(paper_id)}.json"
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        await asyncio.to_thread(atomic_write_text, path, content)

    async def generate_wordcloud_from_comments(self):
        """
        Generate wordcloud from comments data
        Only works when ENABLE_GET_WORDCLOUD and ENABLE_GET_COMMENTS are True
        """
        if not config.ENABLE_GET_WORDCLOUD or not config.ENABLE_GET_COMMENTS:
            return

        if not self.wordcloud_generator:
            return

        try:
            # Read comments from JSON or JSONL file
            comments_data = []
            jsonl_file_path = self._get_file_path('jsonl', 'comments')
            json_file_path = self._get_file_path('json', 'comments')

            if os.path.exists(jsonl_file_path) and os.path.getsize(jsonl_file_path) > 0:
                async with aiofiles.open(jsonl_file_path, 'r', encoding='utf-8') as f:
                    async for line in f:
                        line = line.strip()
                        if line:
                            try:
                                comments_data.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
            elif os.path.exists(json_file_path) and os.path.getsize(json_file_path) > 0:
                async with aiofiles.open(json_file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content:
                        comments_data = json.loads(content)
                        if not isinstance(comments_data, list):
                            comments_data = [comments_data]

            if not comments_data:
                utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] No comments data found")
                return

            # Filter comments data to only include 'content' field
            # Handle different comment data structures across platforms
            filtered_data = []
            for comment in comments_data:
                if isinstance(comment, dict):
                    # Try different possible content field names
                    content_text = comment.get('content') or comment.get('comment_text') or comment.get('text') or ''
                    if content_text:
                        filtered_data.append({'content': content_text})

            if not filtered_data:
                utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] No valid comment content found")
                return

            # Generate wordcloud
            words_base_path = str(kb_source_dir(self.platform, "words"))
            pathlib.Path(words_base_path).mkdir(parents=True, exist_ok=True)
            keyword_label = re.sub(r'[<>:"/\\|?*\r\n]+', '_', str(config.KEYWORDS or 'all')).strip(' ._')
            keyword_label = re.sub(r"_+", "_", keyword_label)[:80] or "all"
            words_file_prefix = f"{words_base_path}/{self.crawler_type}_{keyword_label}_comments_{utils.get_current_date()}"

            utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] Generating wordcloud from {len(filtered_data)} comments")
            await self.wordcloud_generator.generate_word_frequency_and_cloud(filtered_data, words_file_prefix)
            utils.logger.info(f"[AsyncFileWriter.generate_wordcloud_from_comments] Wordcloud generated successfully at {words_file_prefix}")

        except Exception as e:
            utils.logger.error(f"[AsyncFileWriter.generate_wordcloud_from_comments] Error generating wordcloud: {e}")
