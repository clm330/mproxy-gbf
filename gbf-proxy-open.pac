function FindProxyForURL(url, host) {
	if (shExpMatch(url, "*.granbluefantasy.jp/*")
		&& !shExpMatch(url, "*game.granbluefantasy.jp/(authentication|ob/r)*")) {
		return "PROXY 49.234.5.62:18888";
	}
	
	return "DIRECT";
}
