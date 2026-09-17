import {
  expect,
  test,
} from "@playwright/test";


const API =
  "http://127.0.0.1:8000/api/v1";


test.describe(
  "BlockSikka full-stack health",
  () => {
    test(
      "Besu/QBFT backend is healthy",
      async ({
        request,
      }) => {
        const response =
          await request.get(
            `${API}/health`,
          );

        expect(
          response.ok(),
        ).toBeTruthy();

        const body =
          await response.json();

        expect(
          body.connected,
        ).toBe(true);

        expect(
          body.chain_id,
        ).toBe(1337);

        expect(
          body.syncing,
        ).toBe(false);

        expect(
          body.validators,
        ).toHaveLength(4);

        expect(
          body.peer_count,
        ).toBe(3);
      },
    );


    test(
      "PostgreSQL is healthy",
      async ({
        request,
      }) => {
        const response =
          await request.get(
            `${API}/health/database`,
          );

        expect(
          response.ok(),
        ).toBeTruthy();

        const body =
          await response.json();

        expect(
          body.connected,
        ).toBe(true);

        expect(
          body.database,
        ).toBe(
          "blocksikka",
        );
      },
    );


    test(
      "public config describes BlockSikka",
      async ({
        request,
      }) => {
        const response =
          await request.get(
            `${API}/config/public`,
          );

        expect(
          response.ok(),
        ).toBeTruthy();

        const body =
          await response.json();

        expect(
          body.chain_id,
        ).toBe(1337);

        expect(
          body.network_name,
        ).toBe(
          "BlockSikka Local",
        );

        expect(
          body.token.name,
        ).toBe("Sikka");

        expect(
          body.token.symbol,
        ).toBe("SIKKA");

        expect(
          body.token.decimals,
        ).toBe(6);

        expect(
          body
            .payment_processor_address,
        ).toMatch(
          /^0x[a-fA-F0-9]{40}$/,
        );
      },
    );


    test(
      "indexer has initialized",
      async ({
        request,
      }) => {
        const response =
          await request.get(
            `${API}/indexer/status`,
          );

        expect(
          response.ok(),
        ).toBeTruthy();

        const body =
          await response.json();

        expect(
          body.initialized,
        ).toBe(true);

        expect(
          body.last_indexed_block,
        ).not.toBeNull();

        expect(
          body.chain_head,
        ).toBeGreaterThan(0);

        expect(
          body.lag_blocks,
        ).toBeGreaterThanOrEqual(
          0,
        );
      },
    );
  },
);
