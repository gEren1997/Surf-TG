from os.path import splitext
import re
from bot.config import Telegram
from bot.helper.database import Database
from bot.telegram import StreamBot, UserBot
from bot.helper.file_size import get_readable_file_size
from bot.helper.cache import get_cache, save_cache
from asyncio import gather

db = Database()

async def fetch_message(chat_id, message_id):
    try:
        message = await StreamBot.get_messages(chat_id, message_id)
        return message
    except Exception as e:
        return None

async def get_messages(chat_id, first_message_id, last_message_id, batch_size=50):
    messages = []
    current_message_id = first_message_id
    while current_message_id <= last_message_id:
        batch_message_ids = list(range(current_message_id, min(current_message_id + batch_size, last_message_id + 1)))
        tasks = [fetch_message(chat_id, message_id) for message_id in batch_message_ids]
        batch_messages = await gather(*tasks)
        for message in batch_messages:
            if message:
                if file := message.video or message.document:
                    title = file.file_name or message.caption or file.file_id
                    title, _ = splitext(title)
                    title = re.sub(r'[.,|_\\,\']', ' ', title)
                    messages.append({"msg_id": message.id, "title": title,
                                     "hash": file.file_unique_id[:6], "size": get_readable_file_size(file.file_size),
                                     "type": file.mime_type, "chat_id": str(chat_id)})
        current_message_id += batch_size
    return messages

async def get_files(chat_id, page=1):
    if Telegram.SESSION_STRING == '':
        return await db.list_tgfiles(id=chat_id, page=page)
    if cache := get_cache(chat_id, int(page)):
        return cache
    posts = []
    async for post in UserBot.get_chat_history(chat_id=int(chat_id), limit=50, offset=(int(page) - 1) * 50):
        file = post.video or post.document
        if not file:
            continue
        title = file.file_name or post.caption or file.file_id
        title, _ = splitext(title)
        title = re.sub(r'[.,|_\\,\']', ' ', title)
        posts.append({"msg_id": post.id, "title": title,
                      "hash": file.file_unique_id[:6], "size": get_readable_file_size(file.file_size), "type": file.mime_type})
    save_cache(chat_id, {"posts": posts}, page)
    return posts

async def posts_file(posts, chat_id):
    # Modified to support TMDB poster images
    phtml = """
    <div class="col">
        <div class="card shadow-sm">
            <a href="/watch/{chat_id}?id={id}&hash={hash}" class="text-decoration-none text-reset">
                <img src="{img}" class="bd-placeholder-img card-img-top" width="100%" height="225" alt="{title}" style="object-fit: cover;">
                <div class="card-body">
                    <p class="card-text">{title}</p>
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="btn-group">
                            <span class="badge bg-primary rounded-pill">{type}</span>
                            <span class="badge bg-secondary rounded-pill ms-1">{size}</span>
                        </div>
                    </div>
                </div>
            </a>
        </div>
    </div>
    """
    
    # Support for TMDB data in posts
    html_parts = []
    for post in posts:
        img_url = f"/api/thumb/{chat_id}?id={post['msg_id']}"
        
        # Use TMDB poster if available
        if post.get('tmdb_data') and post['tmdb_data'].get('poster'):
            img_url = post['tmdb_data']['poster']
        
        html_parts.append(phtml.format(
            chat_id=str(chat_id).replace("-100", ""),
            id=post["msg_id"],
            img=img_url,
            title=post["title"],
            hash=post["hash"],
            size=post['size'],
            type=post['type']
        ))
    
    return ''.join(html_parts)
