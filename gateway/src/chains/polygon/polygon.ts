import abi from '../../services/ethereum.abi.json';
import axios from 'axios';
import { logger } from '../../services/logger';
import { Contract, Transaction, Wallet } from 'ethers';
import { EthereumBase } from '../../services/ethereum-base';
import { ConfigManager } from '../../services/config-manager';
import { Provider } from '@ethersproject/abstract-provider';
import { Ethereumish } from '../../services/ethereumish.interface';
import {PolygonConfig} from "./polygon.config";
import {QuickswapConfig} from "./quickswap/quickswap.config";

export class Polygon extends EthereumBase implements Ethereumish {
  private static _instance: Polygon;
  private _ethGasStationUrl: string;
  private _gasPrice: number;
  private _gasPriceLastUpdated: Date | null;
  private _nativeTokenSymbol: string;
  private _chain: string;
  private _requestCount: number;
  private _metricsLogInterval: number;

  private constructor() {
    let config;
    switch (ConfigManager.config.POLYGON_CHAIN) {
      case 'matic':
        config = PolygonConfig.config.matic;
        break;
      case 'mumbai':
        config = PolygonConfig.config.mumbai;
        break;
      default:
        throw new Error('POLYGON_CHAIN not valid');
    }

    super(
      'polygon',
      config.chainId,
      config.rpcUrl + ConfigManager.config.MATIC_KEY,
      config.tokenListSource,
      config.tokenListType,
      ConfigManager.config.ETH_MANUAL_GAS_PRICE
    );
    this._chain = ConfigManager.config.POLYGON_CHAIN;
    this._nativeTokenSymbol = 'MATIC';
    this._ethGasStationUrl =
      'https://gasstation-mainnet.matic.network/';
    this._gasPrice = ConfigManager.config.ETH_MANUAL_GAS_PRICE;
    this._gasPriceLastUpdated = null;

    this.updateGasPrice();

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes

    this.onDebugMessage(this.requestCounter.bind(this));
    setInterval(this.metricLogger.bind(this), this.metricsLogInterval);
  }

  public static getInstance(): Polygon {
    if (!Polygon._instance) {
      Polygon._instance = new Polygon();
    }

    return Polygon._instance;
  }

  public static reload(): Polygon {
    Polygon._instance = new Polygon();
    return Polygon._instance;
  }

  public requestCounter(msg: any): void {
    if (msg.action === 'request') this._requestCount += 1;
  }

  public metricLogger(): void {
    logger.info(
      this.requestCount +
        ' request(s) sent in last ' +
        this.metricsLogInterval / 1000 +
        ' seconds.'
    );
    this._requestCount = 0; // reset
  }

  // getters
  public get gasPrice(): number {
    return this._gasPrice;
  }

  public get chain(): string {
    return this._chain;
  }

  public get nativeTokenSymbol(): string {
    return this._nativeTokenSymbol;
  }

  public get gasPriceLastDated(): Date | null {
    return this._gasPriceLastUpdated;
  }

  public get requestCount(): number {
    return this._requestCount;
  }

  public get metricsLogInterval(): number {
    return this._metricsLogInterval;
  }

  // If ConfigManager.config.ETH_GAS_STATION_ENABLE is true this will
  // continually update the gas price.
  async updateGasPrice(): Promise<void> {
    if (ConfigManager.config.ETH_GAS_STATION_ENABLE) {
      const { data } = await axios.get(this._ethGasStationUrl);

      // divide by 10 to convert it to Gwei
      this._gasPrice =
        data[ConfigManager.config.ETH_GAS_STATION_GAS_LEVEL] / 10;
      this._gasPriceLastUpdated = new Date();

      setTimeout(
        this.updateGasPrice.bind(this),
        ConfigManager.config.ETH_GAS_STATION_REFRESH_TIME * 1000
      );
    }
  }

  getContract(
    tokenAddress: string,
    signerOrProvider?: Wallet | Provider
  ): Contract {
    return new Contract(tokenAddress, abi.ERC20Abi, signerOrProvider);
  }

  getSpender(reqSpender: string): string {
    let spender: string;
    if (reqSpender === 'polygon') {
      if (ConfigManager.config.POLYGON_CHAIN === 'matic') {
        spender = QuickswapConfig.config.matic.quickswapV2RouterAddress;
      } else {
        spender = QuickswapConfig.config.mumbai.quickswapV2RouterAddress;
      }
    } else {
      spender = reqSpender;
    }
    return spender;
  }

  // cancel transaction
  async cancelTx(wallet: Wallet, nonce: number): Promise<Transaction> {
    logger.info(
      'Canceling any existing transaction(s) with nonce number ' + nonce + '.'
    );
    return super.cancelTx(wallet, nonce, this._gasPrice);
  }
}
