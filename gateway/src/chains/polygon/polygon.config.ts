import { NetworkConfig } from '../ethereum/ethereum.config';

export interface PolygonNetworksConfig {
  matic: NetworkConfig;
  mumbai: NetworkConfig;
}
export namespace PolygonConfig {
  export const config: PolygonNetworksConfig = {
    matic: {
      chainId: 137,
      rpcUrl: 'https://rpc-mainnet.maticvigil.com/v1/',
      tokenListType: 'FILE',
      tokenListSource:
        'https://wispy-bird-88a7.uniswap.workers.dev/?url=http://tokens.1inch.eth.link',
    },
    mumbai: {
      chainId: 80001,
      rpcUrl: 'https://rpc-mumbai.maticvigil.com/v1/',
      tokenListType: 'FILE',
      tokenListSource: 'src/chains/ethereum/erc20_tokens_kovan.json',
    },
  };
}
