import re

def format_number(number):
    """Форматирует число с разделителями тысяч"""
    return f"{number:,}".replace(",", ".")


def pointer_to_screen_name(user_pointer: str) -> str | None:
    # Remove leading 'vk.com/' from the URL
    if user_pointer.startswith('vk.com/'):
        user_pointer = user_pointer[6:]

    # Match VK links in the format https://vk.com/idXXX or vk.com/idXXX
    vk_link_match = re.match(r'https?:\/\/(?:www\.)?vk\.com\/(.*?)(?:\/|$)', user_pointer)

    # If it's a VK link, extract the ID
    if vk_link_match:
        return vk_link_match.group(1)

    try:
        # Match mentions in the format [idXXX|@mention]
        mention_match = user_pointer.split("|")[0][1:].replace("id", "")
        return mention_match
    except Exception:
        return
