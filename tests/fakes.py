from types import SimpleNamespace


class FakeBlob:
    BASE = "https://teststore.public.blob.vercel-storage.com/"

    def __init__(self):
        self.files, self.deleted = {}, []

    def put_blob(self, pathname, body, access, content_type=None, cache_control_max_age=None, **kw):
        assert access == "public"
        url = self.BASE + pathname
        self.files[url] = (bytes(body), content_type, cache_control_max_age)
        return SimpleNamespace(url=url, pathname=pathname)

    def delete_blob(self, target):
        for t in (target if isinstance(target, list) else [target]):
            self.deleted.append(t)
            self.files.pop(t, None)
