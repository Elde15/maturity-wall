from mwall.clean.geography import _county_name, addr_key, clean_street, zip5


def test_zip5():
    assert zip5("90012") == "90012"
    assert zip5("90012-1234") == "90012"
    assert zip5("6103") == "06103"  # leading zero lost in a spreadsheet
    assert zip5("06103.0") == "06103"
    assert zip5(None) is None
    assert zip5(float("nan")) is None
    assert zip5("123") is None


def test_clean_street():
    assert clean_street("1000-1010 Main St", "TX") == ("1000 MAIN ST", "range to first number")
    assert clean_street("67-76 Booth Street", "NY") == ("67-76 BOOTH STREET", "")  # Queens house number
    assert clean_street("5327 &amp; 5423 Tex-Con Road", "TX")[0] == "5327 TEX-CON ROAD"
    assert clean_street("350 and 450 Water Street", "MA")[0] == "350 WATER STREET"
    assert clean_street("100 Main St (aka The Plaza)", "CA")[0] == "100 MAIN ST"
    assert clean_street("Various", "CA") == (None, "no street address")
    assert clean_street(None, "CA") == (None, "no street address")


def test_addr_key_ignores_case_and_spacing():
    a = addr_key("2700 Potomac Mills Circle", "Woodbridge", "VA", "22192")
    b = addr_key("2700  POTOMAC MILLS CIRCLE ", "woodbridge", "va", "22192-0001")
    assert a == b and len(a) == 16


def test_county_name():
    assert _county_name("Los Angeles County") == "LOS ANGELES"
    assert _county_name("St. Louis") == _county_name("Saint Louis") == "ST LOUIS"
    assert _county_name("Orleans Parish") == "ORLEANS"
