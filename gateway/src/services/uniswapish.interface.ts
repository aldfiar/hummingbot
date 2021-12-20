import { CurrencyAmount, Token, Trade } from '@uniswap/sdk';
import {
  CurrencyAmount as CurrencyAmountPolygon,
  Token as TokenPolygon,
  Trade as TradePolygon,
} from 'quickswap-sdk';
import {
  Token as TokenPangolin,
  CurrencyAmount as CurrencyAmountPangolin,
  Trade as TradePangolin,
} from '@pangolindex/sdk';

import { BigNumber, ContractInterface, Transaction, Wallet } from 'ethers';

export interface ExpectedTrade {
  trade: Trade | TradePangolin | TradePolygon;
  expectedAmount: CurrencyAmount | CurrencyAmountPangolin | CurrencyAmountPolygon;
}

export interface Uniswapish {
  router: string;
  routerAbi: ContractInterface;
  gasLimit: number;
  ttl: number;
  getTokenByAddress(address: string): Token | TokenPangolin | TokenPolygon;
  priceSwapIn(
    baseToken: Token | TokenPangolin | TokenPolygon,
    quoteToken: Token | TokenPangolin |TokenPolygon,
    amount: BigNumber
  ): Promise<ExpectedTrade | string>;
  priceSwapOut(
    quoteToken: Token | TokenPangolin | TokenPolygon,
    baseToken: Token | TokenPangolin | TokenPolygon,
    amount: BigNumber
  ): Promise<ExpectedTrade | string>;
  executeTrade(
    wallet: Wallet,
    trade: Trade | TradePangolin | TradePolygon,
    gasPrice: number,
    uniswapRouter: string,
    ttl: number,
    abi: ContractInterface,
    gasLimit: number,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction>;
}
