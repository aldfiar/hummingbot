import { Router, Request, Response } from 'express';
import { ConfigManager } from '../../../services/config-manager';
import { asyncHandler } from '../../../services/error-handler';
import { Polygon } from '../polygon';
import { price, trade } from './quickswap.controllers';
import { verifyEthereumIsAvailable } from '../polygon-middlewares';
import { verifyQuickswapIsAvailable } from './quickswap-middlewares';
import {
  UniswapPriceRequest,
  UniswapPriceResponse,
  UniswapTradeRequest,
  UniswapTradeResponse,
  UniswapTradeErrorResponse,
} from '../../ethereum/uniswap/uniswap.requests';
import {
  validateUniswapPriceRequest,
  validateUniswapTradeRequest,
} from '../../ethereum/uniswap/uniswap.validators';
import {Quickswap} from "./quickswap";

export namespace QuickSwapRoutes {
  export const router = Router();
  export const ethereum = Polygon.getInstance();
  export const uniswap = Quickswap.getInstance();

  router.use(
    asyncHandler(verifyEthereumIsAvailable),
    asyncHandler(verifyQuickswapIsAvailable)
  );

  router.get('/', async (_req: Request, res: Response) => {
    res.status(200).json({
      network: ConfigManager.config.ETHEREUM_CHAIN,
      uniswap_router: uniswap.router,
      connection: true,
      timestamp: Date.now(),
    });
  });

  router.post(
    '/price',
    asyncHandler(
      async (
        req: Request<unknown, unknown, UniswapPriceRequest>,
        res: Response<UniswapPriceResponse, any>
      ) => {
        validateUniswapPriceRequest(req.body);
        res.status(200).json(await price(ethereum, uniswap, req.body));
      }
    )
  );

  router.post(
    '/trade',
    asyncHandler(
      async (
        req: Request<unknown, unknown, UniswapTradeRequest>,
        res: Response<UniswapTradeResponse | UniswapTradeErrorResponse, any>
      ) => {
        validateUniswapTradeRequest(req.body);
        res.status(200).json(await trade(ethereum, uniswap, req.body));
      }
    )
  );
}
