import os
import sys

import django

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sxdevops.settings')
django.setup()

from cmdb.demo_seed import seed_cmdb_demo


if __name__ == '__main__':
    seed_cmdb_demo()
