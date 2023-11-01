import json
import os
import openai
from tqdm import tqdm

current_path = os.path.abspath(__file__).rsplit('/', 1)[0]
gpt3_api_keys = json.load(open(f'{current_path}/gpt3_apikeys.json'))
print(gpt3_api_keys)
api_keys = open('/apdcephfs_cq2/share_916081/ttianliang/workspace/mlr/code/apikeys.txt').readlines()
gpt3_api_keys = [l.strip().split('----')[-1] for l in api_keys][-1:]


for api_key in tqdm(gpt3_api_keys):
    try:
        # print('hello')
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=[{'role': 'user', 'content': "Question: Roger has 5 tennis balls. He buys 2 more cans of tennis balls. Each can has 3 tennis balls. How many tennis balls does he have now?\nJibu la Hatua kwa Hatua: Roger alianza kwa mipira 5. Mikebe 2 yenye mipira 3 ya tenisi kila oja ni mipira 6 ya tenisi. 5 + 6 = 11. Jibu ni 11.\n--- 11\n\nQuestion: There were nine computers in the server room. Five more computers were installed each day, from monday to thursday. How many computers are now in the server room?\nJibu la Hatua kwa Hatua: Kuna siku 4 kuanzia Jumatatu mpaka Alhamisi. Kompyuta 5 ziliongezwa kila siku. Hiyo inamaanisha kuwa kwa jumla kompyuta 4 * 5 = 20 ziliongezwa. Kulikuwa na kompyuta 9 mwanzoni, hivyo sasa kuna kompyuta 9 + 20 = 29. Jibu ni 29.\n--- 29\n\nQuestion: Leah had 32 chocolates and her sister had 42. If they ate 35, how many pieces do they have left in total?\nJibu la Hatua kwa Hatua: Lea alikuwa na chokoleti 32 na dadake Leah alikuwa na 42. Hiyo inamaanisha kuwa awali kulikuwa na chokoleti 32 + 42 + 74. 35 zimeliwa. Hivyo kwa jumla bado kuna chokoleti 74 - 35 = 39. Jibu ni 39.\n--- 39\n\nQuestion: Shawn has five toys. For Christmas, he got two toys each from his mom and dad. How many toys does he have now?\nJibu la Hatua kwa Hatua: Ana wanasesere 5. Alipata 2 kutoka kwa mama, hivyo baada ya hapo alikuwa na wanasesere 5 + 2 = 7. Kisha alipata 2 zaidi kutoka kwa baba, hivyo kwa jumla alikuwa na wanasesere 7 + 2 = 9. Jibu ni 9.\n--- 9\n\nQuestion: Michael had 58 golf balls. On tuesday, he lost 23 golf balls. On wednesday, he lost 2 more. How many golf balls did he have at the end of wednesday?\nJibu la Hatua kwa Hatua: Michael alianza na mipira 58 ya gofu na akapoteza 23, hivyo ana 58 - 23 = 35. Baadaye alipoteza 2 zaidi, sasa ana mipira 35 - 2 = 33. Jibu ni 33.\n--- 33\n\nJanet’s ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins for her friends every day with four. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. How much in dollars does she make every day at the farmers' market?"}, {'role': 'assistant', 'content': "Step-by-Step Solution: Janet's ducks lay 16 eggs per day. She eats 3 for breakfast and bakes muffins with 4 eggs. So, she uses a total of 3 + 4 = 7 eggs every day.\nThis means she has 16 - 7 = 9 eggs left to sell at the farmers' market.\nSince she sells each egg for $2, she makes 9 * $2 = $18 every day at the farmers' market.\nAnswer: $18."}, {'role': 'user', 'content': "\n\n---"}],
            temperature=0,
            max_tokens=1500,
            api_key=api_key,
            presence_penalty=0.75
        )
        gen = response['choices'][0]['message']['content']
        print(api_key, gen)
    except:
        print(api_key)