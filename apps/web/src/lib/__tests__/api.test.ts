import { api, login, setToken, ApiError } from "@/lib/api";

describe("api client", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    setToken(null);
    jest.restoreAllMocks();
  });

  it("attaches the bearer token to authenticated requests", async () => {
    setToken("test-token-123");
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "1" }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await api.get("/dashboard/summary");

    const [, options] = fetchMock.mock.calls[0];
    const headers = options.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer test-token-123");
  });

  it("does not attach an Authorization header when no token is set", async () => {
    const fetchMock = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) });
    global.fetch = fetchMock as unknown as typeof fetch;

    await api.get("/farms");

    const [, options] = fetchMock.mock.calls[0];
    const headers = options.headers as Headers;
    expect(headers.get("Authorization")).toBeNull();
  });

  it("throws a typed ApiError with the server-provided message on failure", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({ error: { type: "http_error", message: "Farm not found" } }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await expect(api.get("/farms/does-not-exist")).rejects.toMatchObject({
      status: 404,
      message: "Farm not found",
    });
  });

  it("falls back to a generic message when the error body is unparsable", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("not json");
      },
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await expect(api.get("/anything")).rejects.toBeInstanceOf(ApiError);
  });

  it("returns undefined for 204 No Content responses without parsing a body", async () => {
    const fetchMock = jest.fn().mockResolvedValue({ ok: true, status: 204 });
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await api.delete("/farms/1");
    expect(result).toBeUndefined();
  });

  it("sends form-encoded credentials on login and returns the access token", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ access_token: "abc.def.ghi", token_type: "bearer" }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const token = await login("farmer@example.com", "SecurePass1");
    expect(token).toBe("abc.def.ghi");

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers).toMatchObject({ "Content-Type": "application/x-www-form-urlencoded" });
    expect(String(options.body)).toContain("username=farmer%40example.com");
  });

  it("throws ApiError on invalid login credentials", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: { type: "auth_error", message: "Incorrect email or password" } }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    await expect(login("farmer@example.com", "wrong")).rejects.toMatchObject({
      status: 401,
      message: "Incorrect email or password",
    });
  });

  it("does not set a JSON Content-Type header when sending FormData", async () => {
    const fetchMock = jest.fn().mockResolvedValue({ ok: true, status: 201, json: async () => ({}) });
    global.fetch = fetchMock as unknown as typeof fetch;

    const formData = new FormData();
    formData.append("image", new Blob(["x"]), "photo.jpg");
    await api.postForm("/ai/plant-vision/crops/1/detect", formData);

    const [, options] = fetchMock.mock.calls[0];
    const headers = options.headers as Headers;
    expect(headers.get("Content-Type")).toBeNull();
  });
});
