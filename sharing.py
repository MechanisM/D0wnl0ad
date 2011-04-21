#!/usr/bin/env python

import logging
import random
import os.path
import redis

import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
from tornado.options import define, options


class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/([0-9a-f]+)", DownloadHandler),
            (r"/upload", UploadHandler),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=False,
        )
        tornado.web.Application.__init__(self, handlers, **settings)
        self.db = redis.Redis(db=4)


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self): return self.application.db


class MainHandler(BaseHandler):
    def get(self):
        self.render("index.html", share='', filename='')


class UploadHandler(BaseHandler):
    def post(self):
        path = self.get_argument("file.path", None)
        filename = self.get_argument("file.name", None)

        if path and filename:
            random.seed()
            hash = "%016x"%random.getrandbits(128)

            self.db.set('file_path_%s' % hash, os.path.basename(path))
            self.db.expire('file_path_%s' % hash, 60*60*24)

            self.db.set('file_name_%s' % hash, filename)
            self.db.expire('file_name_%s' % hash, 60*60*24)

            self.render("index.html", share=hash, filename=filename)
        else:
            self.render("index.html", share='', filename='')


class DownloadHandler(BaseHandler):
    def get(self, hash):
        path = self.db.get('file_path_%s'%hash)
        if path:
            file_ip = self.db.get('file_ip_%s'%hash)
            if file_ip:
                if file_ip != self.request.remote_ip:
                    raise tornado.web.HTTPError(404)
            else:
                self.db.set('file_ip_%s'%hash, self.request.remote_ip)
                self.db.expire('file_ip_%s' % hash, 60*60*24)
            self.set_header("Content-Type", 'application/octet-stream')
            self.set_header('Content-Disposition', 'attachment; filename=%s' % self.db.get('file_name_%s'%hash))
            self.set_header("X-Accel-Redirect", "/protected/%s" % path)
        else:
            raise tornado.web.HTTPError(404)


def main():
    define("port", default=8988, help="run on the given port", type=int)
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application(), xheaders=True)
    http_server.listen(options.port, '127.0.0.1')
    logging.info('Started at http://127.0.0.1:%s'%options.port)
    tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
    main()