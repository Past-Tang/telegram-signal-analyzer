# -*- coding: utf-8 -*-
"""
Gate.io 合约交易模块
实现基于交易信号的自动化合约交易功能
"""

import gate_api
from gate_api.exceptions import ApiException, GateApiException
import logging
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal, ROUND_DOWN
import asyncio

# 导入配置
from config import GATE_CONFIG, TRADING_CONFIG

# 设置日志
logger = logging.getLogger(__name__)

class GateTrading:
    """Gate.io合约交易类"""

    def __init__(self):
        """初始化Gate.io API客户端"""
        self.configuration = gate_api.Configuration(
            host=GATE_CONFIG['HOST'],
            key=GATE_CONFIG['API_KEY'],
            secret=GATE_CONFIG['API_SECRET']
        )
        self.api_client = gate_api.ApiClient(self.configuration)
        self.futures_api = gate_api.FuturesApi(self.api_client)
        self.settle = GATE_CONFIG['SETTLE']
        self.leverage = GATE_CONFIG['LEVERAGE']
        self.margin_amount = GATE_CONFIG['MARGIN_AMOUNT']

        logger.info(f"Gate.io交易客户端初始化完成 - 结算货币: {self.settle}, 杠杆: {self.leverage}x, 保证金: {self.margin_amount} USDT")

    async def get_contract_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取合约信息"""
        try:
            # 转换交易对格式 (BTC/USDT -> BTC_USDT) 并转换为大写
            contract = symbol.replace('/', '_').upper()

            # 使用异步方式调用API
            response = await asyncio.to_thread(self.futures_api.get_futures_contract, self.settle, contract)

            contract_info = {
                'name': response.name,
                'leverage_min': float(response.leverage_min),
                'leverage_max': float(response.leverage_max),
                'order_size_min': response.order_size_min,
                'order_size_max': response.order_size_max,
                'order_price_round': response.order_price_round,
                'mark_price': float(response.mark_price),
                'last_price': float(response.last_price)
            }

            logger.info(f"获取合约信息成功: {contract} - 当前价格: {contract_info['last_price']}")
            return contract_info

        except (GateApiException, ApiException) as e:
            logger.error(f"获取合约信息失败 {symbol}: {e}")
            return None

    def calculate_position_size(self, symbol: str, entry_price: float) -> int:
        """根据固定保证金计算仓位大小"""
        try:
            # 计算名义价值 = 保证金 * 杠杆
            notional_value = self.margin_amount * self.leverage

            # 计算合约数量 = 名义价值 / 入场价格
            raw_position_size = notional_value / entry_price
            position_size = int(raw_position_size)

            # 如果计算结果小于1，至少设置为1个合约
            if position_size < 1 and raw_position_size > 0:
                position_size = 1
                print(f"⚠️ 计算出的仓位大小小于1，调整为最小值1")

            print(f"仓位计算详情:")
            print(f"  保证金: {self.margin_amount} USDT")
            print(f"  杠杆: {self.leverage}x")
            print(f"  名义价值: {notional_value} USDT")
            print(f"  入场价格: {entry_price}")
            print(f"  原始计算结果: {raw_position_size:.4f}")
            print(f"  最终仓位大小: {position_size}")

            logger.info(f"计算仓位大小: {symbol} - 入场价格: {entry_price}, 仓位大小: {position_size}")

            return position_size

        except Exception as e:
            print(f"❌ 仓位大小计算异常: {e}")
            logger.error(f"计算仓位大小失败: {e}")
            return 0

    async def create_market_order(self, symbol: str, direction: str, size: int) -> Optional[Dict[str, Any]]:
        """创建市价单"""
        try:
            # 转换交易对格式并转换为大写
            contract = symbol.replace('/', '_').upper()

            # 根据方向设置订单大小（正数为买入，负数为卖出）
            order_size = size if direction == 'long' else -size

            # 创建市价单
            futures_order = gate_api.FuturesOrder(
                contract=contract,
                size=order_size,
                price='0',  # 市价单价格设为0
                tif='ioc'   # 立即成交或取消
            )

            # 使用异步方式调用API
            response = await asyncio.to_thread(self.futures_api.create_futures_order, self.settle, futures_order)

            order_info = {
                'order_id': response.id,
                'contract': response.contract,
                'size': response.size,
                'price': response.price,
                'status': response.status,
                'create_time': response.create_time
            }

            logger.info(f"市价单创建成功: {contract} - 方向: {direction}, 数量: {size}, 订单ID: {response.id}")
            return order_info

        except (GateApiException, ApiException) as e:
            logger.error(f"创建市价单失败 {symbol}: {e}")
            return None

    async def create_limit_order(self, symbol: str, direction: str, size: int, price: float) -> Optional[Dict[str, Any]]:
        """创建限价单"""
        try:
            # 转换交易对格式并转换为大写
            contract = symbol.replace('/', '_').upper()

            # 根据方向设置订单大小
            order_size = size if direction == 'long' else -size

            # 创建限价单
            futures_order = gate_api.FuturesOrder(
                contract=contract,
                size=order_size,
                price=str(price),
                tif='gtc'  # 有效直到取消
            )

            # 使用异步方式调用API
            response = await asyncio.to_thread(self.futures_api.create_futures_order, self.settle, futures_order)

            order_info = {
                'order_id': response.id,
                'contract': response.contract,
                'size': response.size,
                'price': response.price,
                'status': response.status,
                'create_time': response.create_time
            }

            logger.info(f"限价单创建成功: {contract} - 方向: {direction}, 数量: {size}, 价格: {price}, 订单ID: {response.id}")
            return order_info

        except (GateApiException, ApiException) as e:
            logger.error(f"创建限价单失败 {symbol}: {e}")
            return None

    async def create_stop_order(self, symbol: str, direction: str, size: int, trigger_price: float, order_price: float = None) -> Optional[Dict[str, Any]]:
        """创建止盈止损单"""
        try:
            # 转换交易对格式并转换为大写
            contract = symbol.replace('/', '_').upper()

            # 根据方向设置订单大小（止盈止损单与开仓方向相反）
            order_size = -size if direction == 'long' else size

            # 创建初始订单（用于止盈止损）
            initial_order = gate_api.FuturesInitialOrder(
                contract=contract,
                size=0,  # 平仓订单size必须为0
                price=str(order_price) if order_price else '0',  # 0表示市价单
                close=True,  # 平仓标志
                reduce_only=True,  # 只减仓
                tif='ioc' if not order_price else 'gtc'  # 市价单必须使用ioc
            )

            # 获取当前价格来判断触发规则
            current_price = (await self.get_contract_info(symbol))['last_price']

            # 创建价格触发器 - 修复参数和逻辑
            # 对于止损：多头止损用<=，空头止损用>=
            # 对于止盈：多头止盈用>=，空头止盈用<=
            if (direction == 'long' and trigger_price < current_price) or (direction == 'short' and trigger_price > current_price):
                # 这是止损单
                rule = 2 if direction == 'long' else 1  # 多头止损用<=，空头止损用>=
            else:
                # 这是止盈单
                rule = 1 if direction == 'long' else 2  # 多头止盈用>=，空头止盈用<=

            trigger = gate_api.FuturesPriceTrigger(
                strategy_type=0,  # 价格触发策略
                price_type=0,     # 价格类型：0=最新价格，1=标记价格，2=指数价格
                price=str(trigger_price),
                rule=rule
            )

            # 创建价格触发订单
            price_triggered_order = gate_api.FuturesPriceTriggeredOrder(
                initial=initial_order,
                trigger=trigger
            )

            # 使用异步方式调用API
            response = await asyncio.to_thread(self.futures_api.create_price_triggered_order, self.settle, price_triggered_order)

            order_info = {
                'order_id': getattr(response, 'id', None),
                'status': getattr(response, 'status', 'unknown'),
                'trigger_price': trigger_price,
                'order_price': order_price,
                'create_time': getattr(response, 'create_time', None)
            }

            logger.info(f"止盈止损单创建成功: {contract} - 触发价格: {trigger_price}, 订单ID: {response.id}")
            return order_info

        except (GateApiException, ApiException) as e:
            logger.error(f"创建止盈止损单失败 {symbol}: {e}")
            return None

    async def execute_trading_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行交易信号"""
        try:
            symbol = signal_data['trading_pair']
            direction = signal_data['direction']
            entry_prices = signal_data['entry_price']
            target_prices = signal_data['target_price']
            stop_loss = signal_data['stop_loss']

            logger.info(f"开始执行交易信号: {symbol} - 方向: {direction}")

            # 获取合约信息
            contract_info = await self.get_contract_info(symbol)
            if not contract_info:
                return {'success': False, 'error': '无法获取合约信息'}

            # 处理入场价格 - 新逻辑
            current_price = contract_info['last_price']
            entry_price = None
            is_market_order = False

            # 检查是否包含"现价"
            has_market_price = any(isinstance(p, str) and p == '现价' for p in entry_prices)

            if has_market_price:
                # 如果包含"现价"，使用市价单
                entry_price = current_price
                is_market_order = True
                print(f"检测到'现价'，使用市价单开仓，当前价格: {entry_price}")
            else:
                # 获取所有数值价格
                numeric_prices = [float(p) for p in entry_prices if isinstance(p, (int, float))]

                if len(numeric_prices) >= 2:
                    # 如果有两个或更多价格，使用均价作为限价单价格
                    entry_price = sum(numeric_prices) / len(numeric_prices)
                    print(f"使用价格范围均价作为限价单价格: {numeric_prices} → {entry_price}")
                elif len(numeric_prices) == 1:
                    # 如果只有一个价格，直接使用
                    entry_price = numeric_prices[0]
                    print(f"使用单一价格作为限价单价格: {entry_price}")
                else:
                    return {'success': False, 'error': '无法确定入场价格：没有有效的价格信息'}

            if entry_price is None:
                return {'success': False, 'error': '无法确定入场价格'}

            # 计算仓位大小
            position_size = self.calculate_position_size(symbol, entry_price)
            if position_size <= 0:
                return {'success': False, 'error': '仓位大小计算错误'}

            results = {
                'success': True,
                'symbol': symbol,
                'direction': direction,
                'entry_price': entry_price,
                'position_size': position_size,
                'orders': []
            }

            # 创建入场订单
            if is_market_order:
                # 市价单入场
                order_result = await self.create_market_order(symbol, direction, position_size)
                if order_result:
                    results['orders'].append({'type': 'market_entry', 'result': order_result})
                else:
                    return {'success': False, 'error': '市价单创建失败'}
            else:
                # 限价单入场
                order_result = await self.create_limit_order(symbol, direction, position_size, entry_price)
                if order_result:
                    results['orders'].append({'type': 'limit_entry', 'result': order_result})
                else:
                    return {'success': False, 'error': '限价单创建失败'}

            # 使用异步等待替代阻塞的sleep
            await asyncio.sleep(0.5)  # 减少等待时间，避免阻塞

            # 创建止损单
            stop_order_result = await self.create_stop_order(symbol, direction, position_size, stop_loss)
            if stop_order_result:
                results['orders'].append({'type': 'stop_loss', 'result': stop_order_result})

            # 创建止盈单 - 根据配置选择模式
            take_profit_price = None

            if TRADING_CONFIG['TAKE_PROFIT_MODE'] == 'first_price' and target_prices:
                # 模式1: 使用第一个目标价格
                take_profit_price = target_prices[0]
                print(f"使用第一个目标价格作为止盈: {take_profit_price}")

            elif TRADING_CONFIG['TAKE_PROFIT_MODE'] == 'percentage':
                # 模式2: 使用百分比计算止盈价格
                percentage = TRADING_CONFIG['TAKE_PROFIT_PERCENTAGE']
                if direction == 'long':
                    # 做多: 入场价格 * (1 + 百分比/100)
                    take_profit_price = entry_price * (1 + percentage / 100)
                else:
                    # 做空: 入场价格 * (1 - 百分比/100)
                    take_profit_price = entry_price * (1 - percentage / 100)
                print(f"使用百分比计算止盈价格: {entry_price} * {percentage}% = {take_profit_price}")

            else:
                print("⚠️ 无效的止盈模式或没有目标价格")

            # 创建止盈单
            if take_profit_price:
                target_order_result = await self.create_stop_order(symbol, direction, position_size, take_profit_price)
                if target_order_result:
                    results['orders'].append({'type': 'take_profit', 'result': target_order_result})
                    print(f"创建止盈单: 价格 {take_profit_price}, 数量 {position_size}")
                else:
                    print(f"❌ 止盈单创建失败: 价格 {take_profit_price}, 数量 {position_size}")
            else:
                print("⚠️ 无法确定止盈价格，跳过止盈单创建")

            logger.info(f"交易信号执行完成: {symbol} - 共创建 {len(results['orders'])} 个订单")
            return results

        except Exception as e:
            logger.error(f"执行交易信号失败: {e}")
            return {'success': False, 'error': str(e)}

async def execute_trade(signal_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行交易的主函数
    供monitor_telegram_trading.py调用
    """
    try:
        trader = GateTrading()
        result = await trader.execute_trading_signal(signal_data)
        return result
    except Exception as e:
        logger.error(f"交易执行失败: {e}")
        return {'success': False, 'error': str(e)}

if __name__ == '__main__':
    # 测试代码
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 测试交易信号
    test_signal = {
        'trading_pair': 'BTC/USDT',
        'direction': 'long',
        'entry_price': ['现价'],
        'target_price': [45000, 46000],
        'stop_loss': 42000
    }

    result = execute_trade(test_signal)
    print(f"测试结果: {result}")