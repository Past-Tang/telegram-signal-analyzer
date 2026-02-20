import json
from openai import OpenAI
from pydantic import BaseModel, ValidationError, model_validator
from typing import List, Optional, Union

# 1. 在 Pydantic 模型中加入自定义逻辑验证
class TradingSignal(BaseModel):
    trading_pair: str
    direction: str
    entry_price: List[Union[str, float]]
    target_price: List[float]
    stop_loss: float

    @model_validator(mode='after')
    def check_prices_logic(self) -> 'TradingSignal':
        """
        验证交易信号中的价格逻辑是否一致。
        - 多单: 目标价应高于入场价，止损价应低于入场价。
        - 空单: 目标价应低于入场价，止损价应高于入场价。
        """
        # 获取一个纯数字的入场价格列表用于比较
        numeric_entry_prices = [p for p in self.entry_price if isinstance(p, (int, float))]
        
        # 如果没有数字价格（例如只有 "现价"），则无法进行逻辑比较，跳过验证
        if not numeric_entry_prices:
            return self

        min_entry = min(numeric_entry_prices)
        max_entry = max(numeric_entry_prices)
        
        min_target = min(self.target_price)
        max_target = max(self.target_price)

        if self.direction == 'long':
            if min_target <= max_entry:
                raise ValueError(f"逻辑冲突 (多单): 最低目标价 {min_target} 必须高于最高入场价 {max_entry}。")
            if self.stop_loss >= min_entry:
                raise ValueError(f"逻辑冲突 (多单): 止损价 {self.stop_loss} 必须低于最低入场价 {min_entry}。")
        
        elif self.direction == 'short':
            if max_target >= min_entry:
                raise ValueError(f"逻辑冲突 (空单): 最高目标价 {max_target} 必须低于最低入场价 {min_entry}。")
            if self.stop_loss <= max_entry:
                raise ValueError(f"逻辑冲突 (空单): 止损价 {self.stop_loss} 必须高于最高入场价 {max_entry}。")
                
        return self

client = OpenAI(
    api_key="sk-gwsjpcyvyoxkpxlvjsdiyvpgikvebombrexdarycsxuqvnec",
    base_url="https://api.siliconflow.cn/v1"
)

# 2. 将核心提取逻辑封装成一个函数
def extract_trade_signal(text: str) -> Optional[TradingSignal]:
    """
    使用 OpenAI 模型从文本中提取交易信号并用 Pydantic 进行验证。
    成功则返回 TradingSignal 对象，失败则返回 None。
    """
    # 增强的提示，包含处理“现价”的例子
    prompt = f"""
你是一个专业的金融交易信号提取助手。
你的任务是从给定的文本中提取交易信息，并严格按照指定的 JSON 格式输出。

这里有四个例子来指导你：

---
例子 1：范围价格 (可执行指令)
- 输入文本:
"BTC 116000-115500附近多
目標 ；117000-118000附近
止損: 114800附近"
- 输出 JSON:
{{
  "trading_pair": "BTC/USDT",
  "direction": "long",
  "entry_price": [116000, 115500],
  "target_price": [117000, 118000],
  "stop_loss": 114800
}}

---
例子 2：现价 (可执行指令)
- 输入文本:
"ETH ；现价轻仓进-3625附近补仓多
目標 ；3674-—3700
止損:3615附近"
- 输出 JSON:
{{
  "trading_pair": "ETH/USDT",
  "direction": "long",
  "entry_price": ["现价", 3625],
  "target_price": [3674, 3700],
  "stop_loss": 3615
}}

---
例子 3：条件性指令 (非可执行指令，应忽略)
- 输入文本:
"白盤留意117100-117600附近不破區間留意多單"
- 输出 JSON:
{{}}

---
例子 4：缺少明确方向 (非可执行指令，应忽略)
- 输入文本:
"移動到116000-116500附近，目標在117000-118000附近，止損在115300附近"
- 输出 JSON:
{{}}
---

现在，请从以下文本中提取交易信号。只提取可直接执行的明确指令。信号必须包含明确的 '多' 或 '空' 方向。对于市场分析、条件性指令、或不完整的信号，请返回一个空的 JSON 对象 {{}}。
---
文本：
{text}
---
"""
    try:
        response = client.chat.completions.create(
            model="Qwen/Qwen3-235B-A22B-Instruct-2507",
            messages=[
                {"role": "system", "content": "You are a helpful assistant designed to output JSON, strictly following the user's specified format."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        
        raw_response = response.choices[0].message.content
        response_data = json.loads(raw_response)
        
        # 预先检查关键字段是否存在，如果不存在或为空，则认为不是有效信号
        required_keys = ["direction", "entry_price", "target_price", "stop_loss"]
        if not response_data or not all(key in response_data for key in required_keys):
            return None

        trade_data = TradingSignal.model_validate(response_data)
        return trade_data

    except ValidationError as e:
        # 直接打印ValidationError的字符串形式，可以更清晰地显示自定义错误
        print(f"  - 数据验证失败: {e}")
        return None
    except (json.JSONDecodeError, IndexError) as e:
        print(f"  - JSON 解析或响应格式错误: {e}")
        return None
    except Exception as e:
        print(f"  - 发生未知错误: {e}")
        return None

# 3. 主程序入口，运行测试用例
if __name__ == "__main__":
    # 全新的、包含50个场景的压力测试集
    test_cases = [
        # Group 1: Valid Signals (15 cases)
        {"description": "Valid Long 1", "text": "ETH  3665-3635附近多\n目標 3695-3730附近\n止損: 3624附近"},
        {"description": "Valid Short 1", "text": "btc 120500-121000附近空\n目標 ；119000-118000附近\n止損: 121700附近"},
        {"description": "Valid Long with '现价'", "text": "ETH ；现价轻仓进-3625附近补仓多\n目標 ；3674-—3700\n止損:3615附近"},
        {"description": "Valid Short 2", "text": "ETH 3810-3840附近空\n目標 3780-3750附近\n止損: 3870附近"},
        {"description": "Valid Long 2", "text": "ETH 3600-3630附近多\n目標 3660-3690附近\n止損: 3570附近"},
        {"description": "Valid Long with 3 TPs", "text": "ETH 3785-3760附近多\n目標 ；3825-3850-3880附近\n止損: 3743附近"},
        {"description": "Valid Short with emoji", "text": "ETH 现价-3720 🈳\n目標 ；3664-3650附近\n止損: 3735附近"},
        {"description": "Valid Long with '市價'", "text": "ETH  市價進附近多-2975附近補倉\n目標 ；3020-3050\n止損:2960"},
        {"description": "Valid Short 3", "text": "ETH ：3000-3020附近空\n目標 ；2960-2970\n止損:3040附近"},
        {"description": "Valid Long 3", "text": "BTC   109700-110300附近多（輕倉）\n目標 ；111500-112000\n止損:109000"},
        {"description": "Valid Short 4", "text": "BTC     110000-110500附近空\n目標 ；109500-108500\n止損:111200"},
        {"description": "Valid Long 4", "text": "eth    2470-2440附近多（穩健）\n目標 ；2500-2530\n止損:2430"},
        {"description": "Valid Short 5", "text": "ETH    2525-2555附近空\n目標 ；2480-2430\n止損:2585"},
        {"description": "Valid Long 5", "text": "BTC    106000-106500附近多\n目標 ；107500-108500\n止損:105300"},
        {"description": "Valid Short with typo in '目標'", "text": "BTC:104500-105000附近空\n目.#$ :103500-102000\n止損: 105700"},

        # Group 2: Invalid Signals - Logical Conflicts (5 cases)
        {"description": "Conflict Long - SL too high", "text": "ETH 3665-3635附近多\n目標 3695-3730附近\n止損: 3700附近"},
        {"description": "Conflict Short - SL too low", "text": "ETH 3810-3840附近空\n目標 3780-3750附近\n止損: 3800附近"},
        {"description": "Conflict Long - TP too low", "text": "BTC ：118300-118800附近多(輕倉)\n目標 ；119800-115000附近\n止損: 117600附近"},
        {"description": "Conflict Short - TP too high", "text": "ETH 3810-3840附近空\n目標 3820-3800附近\n止損: 3870附近"},
        {"description": "Conflict Short - SL inside entry range", "text": "btc 120500-121000附近空\n目標 ；119000-118000附近\n止損: 120600附近"},
         # Group 2: Invalid Signals - Logical Conflicts (5 cases)
        {"description": "Conflict Long - SL too high", "text": "ETH 3665-3635附近多\n目標 3695-3730附近\n止損: 3700附近"},
        {"description": "Conflict Short - SL too low", "text": "ETH 3810-3840附近空\n目標 3780-3750附近\n止損: 3800附近"},
        {"description": "Conflict Long - TP too low", "text": "BTC ：118300-118800附近多(輕倉)\n目標 ；119800-115000附近\n止損: 117600附近"},
        {"description": "Conflict Short - TP too high", "text": "ETH 3810-3840附近空\n目標 3820-3800附近\n止損: 3870附近"},
        {"description": "Conflict Short - SL inside entry range", "text": "btc 120500-121000附近空\n目標 ；119000-118000附近\n止損: 120600附近"},
         # Group 2: Invalid Signals - Logical Conflicts (5 cases)
        {"description": "Conflict Long - SL too high", "text": "ETH 3665-3635附近多\n目標 3695-3730附近\n止損: 3700附近"},
        {"description": "Conflict Short - SL too low", "text": "ETH 3810-3840附近空\n目標 3780-3750附近\n止損: 3800附近"},
        {"description": "Conflict Long - TP too low", "text": "BTC ：118300-118800附近多(輕倉)\n目標 ；119800-115000附近\n止損: 117600附近"},
        {"description": "Conflict Short - TP too high", "text": "ETH 3810-3840附近空\n目標 3820-3800附近\n止損: 3870附近"},
        {"description": "Conflict Short - SL inside entry range", "text": "btc 120500-121000附近空\n目標 ；119000-118000附近\n止損: 120600附近"},
         # Group 2: Invalid Signals - Logical Conflicts (5 cases)
        {"description": "Conflict Long - SL too high", "text": "ETH 3665-3635附近多\n目標 3695-3730附近\n止損: 3700附近"},
        {"description": "Conflict Short - SL too low", "text": "ETH 3810-3840附近空\n目標 3780-3750附近\n止損: 3800附近"},
        {"description": "Conflict Long - TP too low", "text": "BTC ：118300-118800附近多(輕倉)\n目標 ；119800-115000附近\n止損: 117600附近"},
        {"description": "Conflict Short - TP too high", "text": "ETH 3810-3840附近空\n目標 3820-3800附近\n止損: 3870附近"},
        {"description": "Conflict Short - SL inside entry range", "text": "btc 120500-121000附近空\n目標 ；119000-118000附近\n止損: 120600附近"},

        # Group 3: Invalid Signals - Missing/Incomplete Info (10 cases)
        {"description": "Missing Direction 1", "text": "移動到116000-116500附近，目標在117000-118000附近，止損在115300附近"},
        {"description": "Missing Direction 2", "text": "ETH ；3580-3610附近\n目標 ；3640-3670-3700\n止損:3560附近"},
        {"description": "Missing SL", "text": "ETH  3665-3635附近多\n目標 3695-3730附近"},
        {"description": "Missing TP", "text": "ETH  3665-3635附近多\n止損: 3624附近"},
        {"description": "Missing Entry", "text": "ETH 多\n目標 3695-3730附近\n止損: 3624附近"},
        {"description": "Only Direction", "text": "ETH 多"},
        {"description": "Update TPs", "text": "目标修改一下；3070-3090-3120"},
        {"description": "Update SL", "text": "止損放在；3102"},
        {"description": "Vague Entry", "text": "大餅激進的留意119000附近，穩健的119500-112000壓力的都可以去做空..."},
        {"description": "Vague instruction", "text": "空單位置可以在挂一次"},

        # Group 4: Invalid Signals - Conditional (5 cases)
        {"description": "Conditional 1", "text": "白盤留意117100-117600附近不破區間留意多單"},
        {"description": "Conditional 2", "text": "大饼關注118300這裏不破，會繼續走反彈..."},
        {"description": "Conditional 3", "text": "以太破了3750，留意3710-3680附近的支撐，不破，可以留意多單。"},
        {"description": "Conditional 4", "text": "看是否站穩3800，站不穩可以吃波短線"},
        {"description": "Conditional 5", "text": "之前支撐已經破位了"},

        # Group 5: Invalid Signals - Commentary & Noise (15 cases)
        {"description": "Noise - Simple Reply 1", "text": "不拿"},
        {"description": "Noise - Simple Reply 2", "text": "走了"},
        {"description": "Noise - Commentary 1", "text": "50破了。留意3580-3610附近"},
        {"description": "Noise - Trade Management 1", "text": "減倉提損😄😄，今日到位了"},
        {"description": "Noise - Update Average Price", "text": "補了仓均价落到28-31\n60看可以作为top1"},
        {"description": "Noise - Commentary 2", "text": "之前的位置沒走，可以繼續持有，沒有必要在重複進"},
        {"description": "Noise - Commentary 3", "text": "止損就差100點，沒走的，可以在成本價附近走了..."},
        {"description": "Noise - Commentary 4", "text": "我補少了，可以帶著利潤跑了，週末沒啥行情"},
        {"description": "Noise - Cancel Order", "text": "空單先取消，看一下突破情況"},
        {"description": "Noise - Empty Text", "text": ""},
        {"description": "Noise - Random Phrase", "text": "點贊點起來❤️❤️"},
        {"description": "Noise - Question", "text": "還好嗎😂😂，差點到3000。"},
        {"description": "Noise - Commentary 5", "text": "目前在下跌通道內，先關注這裡支撐破了，就留意大級別的支撐在3530-3500附近"},
        {"description": "Noise - Result Announcement", "text": "止盈了。"},
        {"description": "Noise - Commentary 6", "text": "以太真是強勢，留意3630附近，這裡不破還是多頭趨勢"},
        {"description": "Noise - Simple Reply 1", "text": "不拿"},
        {"description": "Noise - Simple Reply 2", "text": "走了"},
        {"description": "Noise - Commentary 1", "text": "50破了。留意3580-3610附近"},
        {"description": "Noise - Trade Management 1", "text": "減倉提損😄😄，今日到位了"},
        {"description": "Noise - Update Average Price", "text": "補了仓均价落到28-31\n60看可以作为top1"},
        {"description": "Noise - Commentary 2", "text": "之前的位置沒走，可以繼續持有，沒有必要在重複進"},
        {"description": "Noise - Commentary 3", "text": "止損就差100點，沒走的，可以在成本價附近走了..."},
        {"description": "Noise - Commentary 4", "text": "我補少了，可以帶著利潤跑了，週末沒啥行情"},
        {"description": "Noise - Cancel Order", "text": "空單先取消，看一下突破情況"},
        {"description": "Noise - Empty Text", "text": ""},
        {"description": "Noise - Random Phrase", "text": "點贊點起來❤️❤️"},
        {"description": "Noise - Question", "text": "還好嗎😂😂，差點到3000。"},
        {"description": "Noise - Commentary 5", "text": "目前在下跌通道內，先關注這裡支撐破了，就留意大級別的支撐在3530-3500附近"},
        {"description": "Noise - Result Announcement", "text": "止盈了。"},
        {"description": "Noise - Commentary 6", "text": "以太真是強勢，留意3630附近，這裡不破還是多頭趨勢"},
        {"description": "Noise - Simple Reply 1", "text": "不拿"},
        {"description": "Noise - Simple Reply 2", "text": "走了"},
        {"description": "Noise - Commentary 1", "text": "50破了。留意3580-3610附近"},
        {"description": "Noise - Trade Management 1", "text": "減倉提損😄😄，今日到位了"},
        {"description": "Noise - Update Average Price", "text": "補了仓均价落到28-31\n60看可以作为top1"},
        {"description": "Noise - Commentary 2", "text": "之前的位置沒走，可以繼續持有，沒有必要在重複進"},
        {"description": "Noise - Commentary 3", "text": "止損就差100點，沒走的，可以在成本價附近走了..."},
        {"description": "Noise - Commentary 4", "text": "我補少了，可以帶著利潤跑了，週末沒啥行情"},
        {"description": "Noise - Cancel Order", "text": "空單先取消，看一下突破情況"},
        {"description": "Noise - Empty Text", "text": ""},
        {"description": "Noise - Random Phrase", "text": "點贊點起來❤️❤️"},
        {"description": "Noise - Question", "text": "還好嗎😂😂，差點到3000。"},
        {"description": "Noise - Commentary 5", "text": "目前在下跌通道內，先關注這裡支撐破了，就留意大級別的支撐在3530-3500附近"},
        {"description": "Noise - Result Announcement", "text": "止盈了。"},
        {"description": "Noise - Commentary 6", "text": "以太真是強勢，留意3630附近，這裡不破還是多頭趨勢"},
        {"description": "Noise - Simple Reply 1", "text": "不拿"},
        {"description": "Noise - Simple Reply 2", "text": "走了"},
        {"description": "Noise - Commentary 1", "text": "50破了。留意3580-3610附近"},
        {"description": "Noise - Trade Management 1", "text": "減倉提損😄😄，今日到位了"},
        {"description": "Noise - Update Average Price", "text": "補了仓均价落到28-31\n60看可以作为top1"},
        {"description": "Noise - Commentary 2", "text": "之前的位置沒走，可以繼續持有，沒有必要在重複進"},
        {"description": "Noise - Commentary 3", "text": "止損就差100點，沒走的，可以在成本價附近走了..."},
        {"description": "Noise - Commentary 4", "text": "我補少了，可以帶著利潤跑了，週末沒啥行情"},
        {"description": "Noise - Cancel Order", "text": "空單先取消，看一下突破情況"},
        {"description": "Noise - Empty Text", "text": ""},
        {"description": "Noise - Random Phrase", "text": "點贊點起來❤️❤️"},
        {"description": "Noise - Question", "text": "還好嗎😂😂，差點到3000。"},
        {"description": "Noise - Commentary 5", "text": "目前在下跌通道內，先關注這裡支撐破了，就留意大級別的支撐在3530-3500附近"},
        {"description": "Noise - Result Announcement", "text": "止盈了。"},
        {"description": "Noise - Commentary 6", "text": "以太真是強勢，留意3630附近，這裡不破還是多頭趨勢"},
    ]
    
    successful_extractions = 0
    total_cases = len(test_cases)
    
    for i, case in enumerate(test_cases):
        print(f"--- [ 测试 {i+1}/{total_cases} ] ---")
        print(f"描述: {case['description']}")
        # 为空文本的测试用例提供一个更清晰的展示
        if case['text']:
            print(f"输入文本:\n---\n{case['text'].strip()}\n---")
        else:
            print("输入文本: [空]")

        signal = extract_trade_signal(case['text'])
        
        if signal:
            successful_extractions += 1
            print("\n✅ 提取成功:")
            print(signal.model_dump_json(indent=4))
        else:
            print("\n❌ 提取失败: 未找到有效交易信号或验证失败。")
        
        print("="*40 + "\n")

    print(f"测试完成。总共 {total_cases} 个测试用例，成功提取 {successful_extractions} 个。")