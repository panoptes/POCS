import os
import os.path
import sys

import glob

from flask import Flask

# sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# from panoptes.utils import has_logger, has_config

# @has_logger
# @has_config
app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello"

@app.route("/images/<directory>/")
def images(directory):
    imgs = glob.glob("/var/panoptes/images/{}/*.jpg".format(directory))
    img_list = '<ul>'
    for img in imgs[0:10]:
        img_list = img_list + '<li><a href="{0}"><img src="{0}" width="100"></img></a></li>\n'.format(img.replace('/var/panoptes/','/static/'))
    img_list = img_list + '</ul>'
    return img_list



if __name__ == '__main__':
    app.run(debug=True)