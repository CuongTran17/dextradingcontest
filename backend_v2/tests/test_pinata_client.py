from src.services.pinata_client import PinataClient


class FakeHttpClient:
    def __init__(self):
        self.requests = []

    def post(self, url, *, headers=None, files=None, json=None):
        self.requests.append(
            {
                "url": url,
                "headers": headers,
                "files": files,
                "json": json,
            }
        )
        return {"IpfsHash": "QmHash"}


def test_upload_json_returns_ipfs_uri():
    http = FakeHttpClient()
    client = PinataClient(jwt="test", http_client=http)

    uri = client.upload_json("metadata.json", {"name": "Certificate"})

    assert uri == "ipfs://QmHash"
    assert http.requests[0]["headers"]["Authorization"] == "Bearer test"
    assert http.requests[0]["json"]["pinataContent"]["name"] == "Certificate"


def test_upload_bytes_returns_ipfs_uri():
    http = FakeHttpClient()
    client = PinataClient(jwt="test", http_client=http)

    uri = client.upload_bytes("certificate.png", b"png", "image/png")

    assert uri == "ipfs://QmHash"
    assert http.requests[0]["files"]["file"][0] == "certificate.png"
    assert http.requests[0]["files"]["file"][2] == "image/png"
