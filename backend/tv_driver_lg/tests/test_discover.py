from tv_driver_lg.discover import extract_tag, parse_headers

SAMPLE_RESPONSE = (
    "HTTP/1.1 200 OK\r\n"
    "CACHE-CONTROL: max-age=1800\r\n"
    "LOCATION: http://192.168.1.40:1754/\r\n"
    "SERVER: WebOS/1.0 UPnP/1.0\r\n"
    "ST: urn:lge-com:service:webos-second-screen:1\r\n"
    "\r\n"
).encode()


def test_parse_headers_upper_cases_keys_and_skips_status_line():
    headers = parse_headers(SAMPLE_RESPONSE)
    assert headers["LOCATION"] == "http://192.168.1.40:1754/"
    assert headers["SERVER"] == "WebOS/1.0 UPnP/1.0"
    assert "HTTP/1.1 200 OK" not in headers


def test_parse_headers_tolerates_blank_and_valueless_lines():
    assert parse_headers(b"NOTIFY * HTTP/1.1\r\nNOCOLON\r\n\r\n") == {}


def test_extract_tag_pulls_inner_text():
    xml = "<root><friendlyName>[LG] webOS TV</friendlyName><modelName>OLED55</modelName></root>"
    assert extract_tag(xml, "friendlyName") == "[LG] webOS TV"
    assert extract_tag(xml, "modelName") == "OLED55"


def test_extract_tag_missing_returns_empty():
    assert extract_tag("<root></root>", "friendlyName") == ""
    assert extract_tag("<friendlyName>unterminated", "friendlyName") == ""
