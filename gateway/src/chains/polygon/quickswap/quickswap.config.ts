export namespace QuickswapConfig {
  export interface QuickswapData {
    quickswapV2RouterAddress: string;
  }

  export interface Config {
    matic: QuickswapData;
    mumbai: QuickswapData;
  }

  export const config: Config = {
    matic: {
      quickswapV2RouterAddress: '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
    },
    mumbai: {
      quickswapV2RouterAddress: '0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D',
    },
  };
}
