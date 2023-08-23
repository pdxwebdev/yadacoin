import os
import sys

from ..test_setup import AsyncTestCase

parent_dir = os.path.abspath(
    os.path.join(
        os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir, os.pardir
    )
)
sys.path.insert(0, parent_dir)
parent_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir, os.pardir)
)
sys.path.insert(0, parent_dir)
parent_dir = os.path.abspath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir)
)
sys.path.insert(0, parent_dir)


class TestNode(AsyncTestCase):
    async def test_scenerio_1(self):
        """One block ahead, no fork"""
