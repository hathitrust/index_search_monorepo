from importlib.resources import files

# Add config files here because the YAML files are in the same directory as this __init__.py file
# TODO add more config variables here if needed
config_queue_file_path = files(__package__) #importlib.resources.files('ht_indexer.config')