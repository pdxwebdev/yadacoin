import sys
import os.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))
print(parent_dir)
sys.path.insert(0, parent_dir)
