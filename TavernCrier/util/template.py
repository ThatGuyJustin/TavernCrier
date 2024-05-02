import yaml


def get_component_template(name):
    with open('./data/components.yaml', 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)

    return raw['components'][name]


def get_embed_template(name):
    with open('./data/components.yaml', 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)

    return raw['embeds'][name]


def get_string_template(name):
    with open('./data/components.yaml', 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)

    return raw['strings'][name]
