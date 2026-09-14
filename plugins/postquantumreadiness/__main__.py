"""
YadaCoin Open Source License (YOSL) v1.1

Run: python -m plugins.postquantumreadiness
"""

from plugins.postquantumreadiness.celery_app import create_celery


def main():
    app = create_celery()
    app.worker_main(["worker", "--loglevel=INFO", "-Q", "celery"])


if __name__ == "__main__":
    main()
