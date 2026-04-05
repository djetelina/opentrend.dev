from opentrend.collectors.chocolatey import ChocolateyCollector

SAMPLE_XML = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
  <entry>
    <content type="application/xml">
      <m:properties>
        <d:Version>2.70.0</d:Version>
        <d:DownloadCount m:type="Edm.Int32">36619</d:DownloadCount>
        <d:VersionDownloadCount m:type="Edm.Int32">5</d:VersionDownloadCount>
      </m:properties>
    </content>
  </entry>
</feed>"""


def test_parse_chocolatey_package() -> None:
    collector = ChocolateyCollector()
    result = collector.parse_package(SAMPLE_XML)
    assert result is not None
    assert result["latest_version"] == "2.70.0"
    assert result["downloads_total"] == 36619


def test_parse_chocolatey_empty() -> None:
    collector = ChocolateyCollector()
    result = collector.parse_package("<feed></feed>")
    assert result is None
