import {
  afterEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";


afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.resetModules();
});


describe(
  "public demo API guard",
  () => {
    it(
      "blocks writes before token access or fetch",
      async () => {
        vi.stubEnv(
          "VITE_PUBLIC_DEMO",
          "true",
        );

        vi.resetModules();

        const fetchMock = vi.fn();

        vi.stubGlobal(
          "fetch",
          fetchMock,
        );

        const storageSpy =
          vi.spyOn(
            Storage.prototype,
            "getItem",
          );

        const { api } =
          await import("./api");

        await expect(
          api.preparePayment({
            from_address:
              "0x0000000000000000000000000000000000000001",
            to_address:
              "0x0000000000000000000000000000000000000002",
            amount: "1",
            expiry: 1,
            payment_id: "0x01",
          }),
        ).rejects.toThrow(
          "This deployment is read-only.",
        );

        expect(
          storageSpy,
        ).not.toHaveBeenCalled();

        expect(
          fetchMock,
        ).not.toHaveBeenCalled();
      },
    );
  },
);
