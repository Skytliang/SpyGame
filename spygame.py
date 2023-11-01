import re
import os
import json
import argparse
import itertools
import random
# random.seed(0)
from utils.agent import TurboPlayer, DavinciPlayer, BardPlayer, VicunaPlayer
from datetime import datetime
from tqdm import tqdm


PRINT_LOG = True

NAME_LIST_ANONYMOUS = ["Player 1", "Player 2", "Player 3", "Player 4", "Player 5", "Player 6", "Player 7", "Player 8", "Player 9", "Player 10"]

SUPPORT_MODELS = ["gpt-4", "gpt-4-0314", "gpt-4-0613", "gpt-3.5-turbo", "gpt-3.5-turbo-0301", "gpt-3.5-turbo-0613", "text-davinci-003", "text-davinci-002", "bard", "vicuna", "fastchat-t5", "longchat"]
SUPPORT_MODELS_WITH_MEMORY_LIST = ["gpt-4", "gpt-4-0314", "gpt-4-0613", "gpt-3.5-turbo", "gpt-3.5-turbo-0301", "gpt-3.5-turbo-0613", "text-davinci-003", "text-davinci-002", "bard"]


def SpyPlayer(model_name: str = None, name: str = None, secret_word: str = None, temperature:float = 0, sleep_time: float = 0):
    assert model_name in SUPPORT_MODELS, f"Not support {model_name}. Choices: {SUPPORT_MODELS}"

    if model_name in ["gpt-4", "gpt-4-0314", "gpt-4-0613", "gpt-3.5-turbo", "gpt-3.5-turbo-0301", "gpt-3.5-turbo-0613"]:
        return TurboPlayer(model_name, name, secret_word, temperature, sleep_time)
    elif model_name in ["text-davinci-003", "text-davinci-002"]:
        return DavinciPlayer(model_name, name, secret_word, temperature, sleep_time)
    elif model_name in ["bard"]:
        return BardPlayer(model_name, name, secret_word, temperature, sleep_time)
    elif model_name in ["vicuna", "fastchat-t5", "longchat"]:
        return VicunaPlayer(model_name, name, secret_word, temperature, sleep_time)


class SpyGame:
    def __init__(self,
            guest_agent: str,
            host_agent: str,
            temperature: float,
            num_players: int,
            max_rounds: int,
            spy_word: str,
            villager_word: str,
            guest_identity: str,
            sleep_time: float,
            prompts: dict,
            seed: int,
            save_file_path: str
        ) -> None:
        
        """Create a spy game

        Args:
            guest_agent (str): guest agent model name
            host_agent (str): host agent model name
            temperature (float): higher values make the output more random, while lower values make it more focused and deterministic
            num_players (int): number of all players
            max_rounds (int): maximum number of game rounds
            spy_word (str): spy agent's keyword
            villager_word (str): villager agent's keyword
            guest_identity (str): identity that guest participate in the game
            sleep_time (float): sleep against rate limiting
        """

        self.temperature = temperature
        self.num_players = num_players
        self.max_rounds = max_rounds
        self.spy_word = spy_word
        self.villager_word = villager_word
        self.prompts = prompts
        self.save_file_path = save_file_path

        self.num_spy = 1
        self.meta_prompt = self.prompts['meta_prompt']
        
        # the secret word list of all players
        self.secret_word_list = [self.spy_word] + [self.villager_word] * (self.num_players - 1)
        random.shuffle(self.secret_word_list)

        spy_order = self.secret_word_list.index(self.spy_word)

        all_order = list(range(self.num_players))
        all_order.remove(spy_order)
        villager_order = random.choice(all_order)

        # init agents
        NAME_LIST = NAME_LIST_ANONYMOUS[: self.num_players]
        random.shuffle(NAME_LIST)
        self.players = [
            SpyPlayer(model_name=host_agent, name=NAME_LIST[idx], secret_word=secret_word, temperature=self.temperature, sleep_time=sleep_time)
                for idx, secret_word in enumerate(self.secret_word_list)
        ]
        
        guest_name = None
        if guest_identity == 'spy':
            spy_player = self.players[spy_order]
            self.players[spy_order] = SpyPlayer(model_name=guest_agent, name=NAME_LIST[spy_order], secret_word=self.spy_word, temperature=self.temperature, sleep_time=sleep_time)
            del spy_player
            guest_name = NAME_LIST[spy_order]
        elif guest_identity == 'villager':
            villager_player = self.players[villager_order]
            self.players[villager_order] = SpyPlayer(model_name=guest_agent, name=NAME_LIST[villager_order], secret_word=self.villager_word, temperature=self.temperature, sleep_time=sleep_time)
            del villager_player
            guest_name = NAME_LIST[villager_order]

        self.spy_name = [player.name for player in self.players if player.secret_word == self.spy_word][0]

        self.player_names = {p.name: p for p in self.players}
        players_model = {p.name: (p.model_name, p.secret_word) for p in self.players}

        self.init_prompt()

        # save file
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d_%H:%M:%S")
        self.save_file = {
            'game_name': 'SpyGame',
            'start_time': current_time,
            'end_time': '',
            'win': "",
            'spy': f"{self.spy_name} ({self.spy_word})",
            'spy_word': self.spy_word,
            'villager_word': self.villager_word,
            'host_agent': host_agent,
            'guest_agent': guest_agent,
            'guest_identity': guest_identity,
            'guest_name': guest_name,
            'temperature': temperature,
            'num_players': num_players,
            'max_rounds': max_rounds,
            'players_model': players_model,
            'seed': seed,
            'rounds': {},
            'players': {},
            'players_idx': {},
            'prompts': prompts
        }

        if PRINT_LOG:
            print(f"spy: {self.spy_name} ({self.spy_word})")
            print(f"players_model: {players_model}")
            print(f"seed: {seed}")

    def init_prompt(self):
        for player in self.players:
            meta_prompt = self.prompts['meta_prompt'].format(name=player.name, num_players=self.num_players, num_spy=self.num_spy, num_villager=self.num_players-self.num_spy, secret_word=player.secret_word)
            player.set_meta_prompt(meta_prompt)
        if PRINT_LOG:
            print(meta_prompt)

    def cot_modify(self, text, phase, round):
        round_dct = {
        1: 'first', 2: 'second', 3: 'third', 4: 'fourth', 5: 'fifth', 6: 'sixth', 7: 'seventh', 8: 'eighth', 9: 'ninth', 10: 'tenth'
            }
        try:
            prompt = f"Here is my thought during the {round_dct[round]} round of the {phase} phase."
        except:
            prompt = f"Here is my thought."
        return prompt + '\n\n' + text
        
    def broadcast(self, msg: str):
        """Broadcast a message to all players. 
        Typical use is for the host to announce public information

        Args:
            msg (str): the message
        """
        if PRINT_LOG:
            print(msg)
        for player in self.players:
            player.add_event(msg)

    def speak(self, speaker: str, msg: str):
        """The speaker broadcast a message to all other players. 

        Args:
            speaker (str): name of the speaker
            msg (str): the message
        """
        if not msg.startswith(f"{speaker}:"):
            msg = f"{speaker}: {msg}"
        if PRINT_LOG:
            print(msg)
        for player in self.players:
            if player.name != speaker:
                player.add_event(msg)

    def save(self):
        now = datetime.now()
        current_time = now.strftime("%Y-%m-%d_%H:%M:%S")
        self.save_file['end_time'] = current_time

        json_str = json.dumps(self.save_file, ensure_ascii=False, indent=4)
        with open(self.save_file_path, 'w') as f:
            f.write(json_str)
        

    def run(self):
        round = 0
        self.tie_restart = False

        self.spy_candidates = self.player_names
        self.villager_candidates = self.player_names
        
        while len(self.players) > 2:
            if round >= self.max_rounds:
                break
            while True:
                if round >= self.max_rounds:
                    break
                if PRINT_LOG:
                    print(f"\n===== Round-{round+1} =====\n")

                # ask for the decription
                describe_cot = {}
                describe_save_dct = {}
                shuffle_names = list(self.spy_candidates.keys())
                random.shuffle(shuffle_names)
                
                self.broadcast(f"Host: It is now the description phase, please take turns to describe the keyword you received in the order of {shuffle_names}.")

                spy_candidates_done = []
                if round != 0:
                    spy_candidates_done = shuffle_names[: ]

                for player_name in shuffle_names:
                    player = self.spy_candidates[player_name]

                    if len(spy_candidates_done) != 0:
                        spy_candidates_done = list(set(spy_candidates_done))
                        spy_candidates_done.sort()
                        
                        # init word prompt
                        num_villager_survive = len(self.players) - 1
                        player_secret_word = player.secret_word

                        word_judgement = self.prompts['word_judgement'].format(options=spy_candidates_done, player_secret_word=player_secret_word, name=player_name, num_villager=len(self.players)-1)
                        
                        # word judgement
                        player.add_event(word_judgement, 1)
                        ans = player.ask()
                        player.add_memory(self.cot_modify(ans, 'description', round+1))
                        describe_cot[player.name] = ans
                    spy_candidates_done.append(player_name)

                    describe_prompt = self.prompts['describe_prompt'].format(name=player.name, secret_word=player.secret_word)
                    player.add_event(describe_prompt, 1)
                    ans = player.ask()

                    # rule-based cleaning secret word
                    ans = ans.replace(player.secret_word, 'My keyword')
                    ans = ans.replace(player.secret_word.lower(), 'my keyword')
                    if not ans.startswith(player_name):
                        ans = f"{player_name}: {ans}"

                    describe_save_dct[player.name] = ans
                    # speak to other players
                    self.speak(player.name, f"{ans}")

                    # add self memory
                    player.add_memory(ans)

                # voting
                vote_cot = {}
                vote_save_dct = {}
                spy_candidates_done = list(self.spy_candidates.keys())
                spy_candidates_done.sort()
                results = {
                    player_name: 0
                    for player_name in spy_candidates_done
                    }
                self.broadcast(f"Host: It is now the voting phase, Please judge the keywords and identities of these alive players {spy_candidates_done}.")
                for player_name in self.villager_candidates:
                    player = self.villager_candidates[player_name]

                    shuffle_names = list(self.spy_candidates.keys())
                    random.shuffle(shuffle_names)
                    
                    # init identity prompt
                    player_secret_word = player.secret_word
                    options = [spy for spy in shuffle_names if spy != player_name]

                    identity_judgement = self.prompts['identity_judgement'].format(options=spy_candidates_done, player_secret_word=player_secret_word, name=player_name, num_villager=len(self.players)-1)
                    
                    # identity judgement
                    player.add_event(identity_judgement, 1)
                    ans = player.ask()
                    player.add_memory(self.cot_modify(ans, 'voting', round+1))
                    vote_cot[player.name] = ans

                    # vote phase
                    vote_prompt = self.prompts['vote_prompt'].format(options=options, name=player_name)
                    player.add_event(vote_prompt, 1)
                    raw_ans = player.ask()
                    
                    # player.add_memory(raw_ans)
                    pattern = '|'.join(options)
                    try:
                        ans = re.findall(pattern=pattern, string=raw_ans)
                        if len(ans) == 1:
                            ans = ans[0]
                        else:
                            ans = None
                    except:
                        ans = None

                    temperature_offset = 0.05
                    current_temperature = player.temperature
                    cnt = 0
                    while ans not in options:
                        cnt += 1
                        if player.model_name in SUPPORT_MODELS_WITH_MEMORY_LIST:
                            player.memory_lst = player.memory_lst[:-3]
                            player.memory_lst_idx = player.memory_lst_idx[:-3]

                            # identity judgement
                            player.add_event(identity_judgement, 1)
                            ans = player.ask(min(current_temperature, 1.0))
                            player.add_memory(self.cot_modify(ans, 'voting', round+1))
                            vote_cot[player.name] = ans

                            # vote phase
                            player.add_event(vote_prompt, 1)
                            raw_ans = player.ask(min(current_temperature, 1.0))

                            try:
                                ans = re.findall(pattern=pattern, string=raw_ans)
                                if len(ans) == 1:
                                    ans = ans[0]
                                else:
                                    ans = None
                                    current_temperature += temperature_offset
                            except:
                                current_temperature += temperature_offset
                        else:
                            try:
                                raw_ans = player.ask(min(current_temperature, 1.0))
                                ans = re.findall(pattern=pattern, string=raw_ans)
                                if len(ans) == 1:
                                    ans = ans[0]
                                else:
                                    current_temperature += temperature_offset
                            except:
                                current_temperature += temperature_offset
                        if cnt >= 3:
                            break
                    player.add_memory(raw_ans, 0)

                    vote_result = self.prompts['vote_result'].format(name1=player.name, name2=ans, response=raw_ans)
                    if PRINT_LOG:
                        print(vote_result)
                    vote_save_dct[player.name] = vote_result

                    results[ans] += 1


                max_value = max(results.values())
                max_keys = [k for k, v in results.items() if v == max_value]
                round += 1
                if len(max_keys) == 1:
                    break
                elif len(max_keys) == len(self.players):
                    broadcast_news = self.prompts['tie_prompt'].format(options=max_keys)
                    self.save_file["rounds"][f"round-{round}"] = {
                        "describe": describe_save_dct,
                        "describe_cot": describe_cot,
                        "vote": vote_save_dct,
                        "vote_cot": vote_cot,
                        "vote_num": results,
                        "result": broadcast_news
                    }
                    self.spy_candidates = self.player_names
                    self.villager_candidates = self.player_names
                else:
                    broadcast_news = self.prompts['tie_prompt'].format(options=max_keys)
                    self.save_file["rounds"][f"round-{round}"] = {
                        "describe": describe_save_dct,
                        "describe_cot": describe_cot,
                        "vote": vote_save_dct,
                        "vote_cot": vote_cot,
                        "vote_num": results,
                        "result": broadcast_news
                    }
                    if self.tie_restart:
                        self.spy_candidates = self.player_names
                        self.villager_candidates = self.player_names
                        self.tie_restart = False
                    else:
                        self.spy_candidates = {name: self.player_names[name] for name in max_keys}
                        self.villager_candidates = {name: self.player_names[name] for name in self.player_names if name not in max_keys}
                        self.tie_restart = True
                if PRINT_LOG:
                    print(broadcast_news)
                self.broadcast(broadcast_news)

            selected_name = max_keys[0]

            # checking state
            break_flag = False
            if selected_name == self.spy_name:
                # game over villager_win
                broadcast_news = self.prompts['villager_win'].format(selected_name=selected_name, spy_word=self.spy_word, villager_word=self.villager_word)
                self.save_file['win'] = 'villager'
                break_flag = True
            elif len(self.players) == 3:
                # game over spy_win
                broadcast_news = self.prompts['spy_win'].format(selected_name=selected_name, spy_name=self.spy_name, spy_word=self.spy_word, villager_word=self.villager_word)
                self.save_file['win'] = 'spy'
                break_flag = True
            else:
                # remove the selected player
                broadcast_news = self.prompts['continue'].format(selected_name=selected_name)
                selected_player = None
                for player in self.players:
                    if player.name == selected_name:
                        selected_player = player
                self.save_file['players'][selected_name] = selected_player.memory_lst
                self.save_file['players_idx'][selected_name] = list(selected_player.memory_lst_idx)
                self.players.remove(selected_player)
                self.player_names.pop(selected_name)
                del selected_player
                self.spy_candidates = self.player_names
                self.villager_candidates = self.player_names
                
            if PRINT_LOG:
                print(broadcast_news)
            self.broadcast(broadcast_news)
            self.save_file["rounds"][f"round-{round}"] = {
                "describe": describe_save_dct,
                "describe_cot": describe_cot,
                "vote": vote_save_dct,
                "vote_cot": vote_cot,
                "vote_num": results,
                "result": broadcast_news
            }
            if break_flag:
                break

        for player in self.players:
            self.save_file['players'][player.name] = player.memory_lst
            self.save_file['players_idx'][player.name] = list(player.memory_lst_idx)
            del player





if __name__ == "__main__":
    
    spygame_path = os.path.abspath(__file__).rsplit('/', 1)[0]
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--keywords-path', type=str, default=f"{spygame_path}/prompt/keyword_set.json")
    parser.add_argument('--prompts-path', type=str, default=f"{spygame_path}/prompt/prompts.json")
    parser.add_argument('--guest-agent', type=str, default='gpt-4-0613')
    parser.add_argument('--host-agent', type=str, default='gpt-3.5-turbo-0613')
    parser.add_argument('--guest-identity', type=str, choices=['spy', 'villager'], default='spy')
    parser.add_argument('--temperature', type=float, default=0.3)
    parser.add_argument('--num-players', type=int, default=4)
    parser.add_argument('--max-rounds', type=int, default=7)
    parser.add_argument('--sleep-time', type=int, default=0)
    args = parser.parse_args()
    
    save_file_dir = spygame_path + f'/benchmark/{args.host_agent}/{args.guest_agent}'
    if not os.path.exists(save_file_dir):
        os.makedirs(save_file_dir)

    keywords = json.load(open(args.keywords_path))
    prompts = json.load(open(args.prompts_path))

    total_files = len(keywords) * 2

    for keyword_pair, i in tqdm(itertools.product(keywords, range(2)), total=total_files):
        
        # try:
            file_name = f'{keyword_pair[i]}.json'
            files = os.listdir(save_file_dir)
            if file_name in files:
                continue
            
            seed = random.randrange(10000)
            random.seed(seed)
            spy_game = SpyGame(
                        guest_agent = args.guest_agent,
                        host_agent = args.host_agent,
                        temperature = args.temperature,
                        num_players = args.num_players,
                        max_rounds = args.max_rounds,
                        spy_word = keyword_pair[i],
                        villager_word = keyword_pair[i-1],
                        guest_identity = args.guest_identity,
                        sleep_time = args.sleep_time,
                        prompts = prompts,
                        seed = seed,
                        save_file_path=f'{save_file_dir}/{file_name}'
                    )
            spy_game.run()
            spy_game.save()

        # except:
        #     pass