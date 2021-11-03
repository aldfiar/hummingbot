import abi from '../../services/ethereum.abi.json';
import axios from 'axios';
import { logger } from '../../services/logger';
import { BigNumber, Contract, Transaction, Wallet, utils } from 'ethers';
import { EthereumBase, Token } from '../../services/ethereum-base';
import { ConfigManager } from '../../services/config-manager';
import { EthereumConfig } from './ethereum.config';
import { TokenValue } from '../../services/base';
import { Provider } from '@ethersproject/abstract-provider';
import { EVMNonceManager } from './evm.nonce';

// MKR does not match the ERC20 perfectly so we need to use a separate ABI.
const MKR_ADDRESS = '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2';

export class Ethereum extends EthereumBase {
  private static _instance: Ethereum;
  private _ethGasStationUrl: string;
  private _gasPrice: number;
  private _gasPriceLastUpdated: Date | null;
  private _nonceManager: EVMNonceManager;
  private _requestCount: number;
  private _metricsLogInterval: number;

  private constructor() {
    let config;
    if (ConfigManager.config.ETHEREUM_CHAIN === 'mainnet') {
      config = EthereumConfig.config.mainnet;
    } else {
      config = EthereumConfig.config.kovan;
    }

    super(
      config.chainId,
      config.rpcUrl + ConfigManager.config.INFURA_KEY,
      config.tokenListSource,
      config.tokenListType,
      ConfigManager.config.ETH_MANUAL_GAS_PRICE
    );

    this._ethGasStationUrl =
      'https://ethgasstation.info/api/ethgasAPI.json?api-key=' +
      ConfigManager.config.ETH_GAS_STATION_API_KEY;

    this._gasPrice = ConfigManager.config.ETH_MANUAL_GAS_PRICE;
    this._gasPriceLastUpdated = null;

    this.updateGasPrice();

    this._nonceManager = EVMNonceManager.getInstance();

    this._requestCount = 0;
    this._metricsLogInterval = 300000; // 5 minutes
  }

  public static getInstance(): Ethereum {
    if (!Ethereum._instance) {
      Ethereum._instance = new Ethereum();
    }

    return Ethereum._instance;
  }

  async init(): Promise<void> {
    if (!this.ready() && !this._initializing) {
      this._initializing = true;
      await this.loadTokens(this.tokenListSource, this.tokenListType);
      await this._nonceManager.init(this.provider, 60, this.chainId);
      this._ready = true;
      this._initializing = false;
      this.onDebugMessage(this.requestCounter.bind(this));
      setInterval(this.metricLogger.bind(this), this.metricsLogInterval);
    }
    return this._initPromise;
  }

  public static reload(): Ethereum {
    Ethereum._instance = new Ethereum();
    return Ethereum._instance;
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

  public get nonceManager() {
    return this._nonceManager;
  }

  public get gasPrice(): number {
    return this._gasPrice;
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

  // ethereum token lists are large. instead of reloading each time with
  // getTokenList, we can read the stored tokenList value from when the
  // object was initiated.
  public get storedTokenList(): Token[] {
    return this._tokenList;
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

  // override getERC20Balance definition to handle MKR edge case
  async getERC20Balance(
    wallet: Wallet,
    tokenAddress: string,
    decimals: number
  ): Promise<TokenValue> {
    // instantiate a contract and pass in provider for read-only access
    const contract = this.getContract(tokenAddress, this.provider);

    logger.info(
      'Requesting balance for owner ' +
        wallet.address +
        ' for token ' +
        tokenAddress +
        '.'
    );
    const balance = await contract.balanceOf(wallet.address);
    logger.info(balance);
    return { value: balance, decimals: decimals };
  }

  // override getERC20Allowance
  async getERC20Allowance(
    wallet: Wallet,
    spender: string,
    tokenAddress: string,
    decimals: number
  ): Promise<TokenValue> {
    // instantiate a contract and pass in provider for read-only access
    const contract = this.getContract(tokenAddress, this.provider);

    logger.info(
      'Requesting spender ' +
        spender +
        ' allowance for owner ' +
        wallet.address +
        ' for token ' +
        tokenAddress +
        '.'
    );
    const allowance = await contract.allowance(wallet.address, spender);
    logger.info(allowance);
    return { value: allowance, decimals: decimals };
  }

  getContract(tokenAddress: string, signerOrProvider?: Wallet | Provider) {
    return tokenAddress === MKR_ADDRESS
      ? new Contract(tokenAddress, abi.MKRAbi, signerOrProvider)
      : new Contract(tokenAddress, abi.ERC20Abi, signerOrProvider);
  }

  // override approveERC20
  async approveERC20(
    wallet: Wallet,
    spender: string,
    tokenAddress: string,
    amount: BigNumber,
    nonce?: number,
    maxFeePerGas?: BigNumber,
    maxPriorityFeePerGas?: BigNumber
  ): Promise<Transaction> {
    // instantiate a contract and pass in wallet, which act on behalf of that signer
    const contract = this.getContract(tokenAddress, wallet);

    logger.info(
      'Calling approve method called for spender ' +
        spender +
        ' requesting allowance ' +
        amount.toString() +
        ' from owner ' +
        wallet.address +
        ' on token ' +
        tokenAddress +
        '.'
    );
    if (!nonce) {
      nonce = await this.nonceManager.getNonce(wallet.address);
    }
    let response;
    if (maxFeePerGas || maxPriorityFeePerGas) {
      response = await contract.approve(spender, amount, {
        gasLimit: 100000,
        nonce: nonce,
        maxFeePerGas,
        maxPriorityFeePerGas,
      });
    } else {
      response = await contract.approve(spender, amount, {
        gasPrice: this._gasPrice * 1e9,
        gasLimit: 100000,
        nonce: nonce,
      });
    }

    logger.info(response);

    await this.nonceManager.commitNonce(wallet.address, nonce);
    return response;
  }

  getTokenBySymbol(tokenSymbol: string): Token | undefined {
    return this._tokenList.find(
      (token: Token) => token.symbol === tokenSymbol.toUpperCase()
    );
  }

  // cancel transaction
  async cancelTx(wallet: Wallet, nonce: number): Promise<Transaction> {
    logger.info(
      'Canceling any existing transaction(s) with nonce number ' + nonce + '.'
    );
    const tx = {
      from: wallet.address,
      to: wallet.address,
      value: utils.parseEther('0'),
      nonce: nonce,
      gasPrice: this._gasPrice * 1e9 * 2,
    };
    const response = await wallet.sendTransaction(tx);
    logger.info(response);

    return response;
  }
}