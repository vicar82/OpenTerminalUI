import { describe, it, expect, afterEach } from "vitest";
import { setAccessTokenGetter, getAccessToken } from "../api/base";

describe("getAccessToken", () => {
  afterEach(() => setAccessTokenGetter(null));

  it("returns null when no getter is registered", () => {
    setAccessTokenGetter(null);
    expect(getAccessToken()).toBeNull();
  });

  it("returns the token from the registered getter", () => {
    setAccessTokenGetter(() => "tok-123");
    expect(getAccessToken()).toBe("tok-123");
  });
});
