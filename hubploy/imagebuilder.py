"""
Builds docker images from directories when necessary
"""
import docker
import argparse
import os
import json
from functools import partial
from hubploy import gitutils
from hubploy.config import get_config
from repo2docker.app import Repo2Docker


def make_imagespec(path, image_name):
    tag = gitutils.last_modified_commit(path)
    if not tag:
        tag = 'latest'
    return f'{image_name}:{tag}'


def build_image(client, path, image_spec, cache_from=None, push=False):
    r2d = Repo2Docker()
    r2d.subdir = path
    r2d.output_image_spec = image_spec
    r2d.user_id = 1000
    r2d.user_name = 'jovyan'
    if cache_from:
        r2d.cache_from = cache_from

    r2d.initialize()
    r2d.build()
    if push:
        r2d.push_image()


def pull_image(client, image_name, tag):
    """
    Pull given docker image
    """
    pull_output = client.api.pull(
        image_name,
        tag,
        stream=True,
        decode=True
    )
    for line in pull_output:
        pass


def pull_images_for_cache(client, path, image_name, commit_range):
    # Pull last built image if we can
    cache_from = []
    for i in range(1, 5):
        image = image_name
        # FIXME: Make this look for last modified since before beginning of commit_range
        tag = gitutils.last_modified_commit(path, n=i)
        try:
            print(f'Trying to pull {image}:{tag}')
            pull_image(client, image, tag)
            cache_from.append(f'{image}:{tag}')
            break
        except Exception as e:
            # Um, ignore if things fail!
            print(str(e))

    return cache_from

def build_if_needed(client, path, image_name, commit_range, push=False):
    image_spec = make_imagespec(path, image_name)

    if (not commit_range) or gitutils.path_touched(path, commit_range=commit_range):
        print(f'Image {image_spec} needs to be built...')

        cache_from = pull_images_for_cache(client, path, image_name, commit_range)
        print(f'Starting to build {image_spec}')
        build_image(client, path, image_spec, cache_from, push)
        return True
    else:
        print(f'Image {image_spec}: already up to date')
        return False

def build_deployment(client, deployment, commit_range, push=False):
    config = get_config(deployment)

    image_path = os.path.abspath(os.path.join('deployments', deployment, 'image'))
    image_name = config['images']['image_name']

    build_if_needed(client, image_path, image_name, commit_range, push)
