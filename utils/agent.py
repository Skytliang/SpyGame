import os
import openai
import backoff
import time
import random
import json
import copy
import numpy as np
from datetime import datetime
from openai.error import RateLimitError, APIError, ServiceUnavailableError, APIConnectionError, AuthenticationError
from utils.openai_utils import OutOfQuotaException, AccessTerminatedException, TimeOutException
from utils.openai_utils import num_tokens_from_string, model2max_context


# from bardapi import Bard
# import requests

# import torch
# from transformers import AutoTokenizer, AutoModelForCausalLM
# from FastChat.fastchat.model.model_adapter import load_model, get_conversation_template, add_model_args

cycle_all_keys = True

current_path = os.path.abspath(__file__).rsplit('/', 1)[0]

gpt3_api_keys = json.load(open(f'{current_path}/gpt3_apikeys.json'))
gpt4_api_keys = json.load(open(f'{current_path}/gpt4_apikeys.json'))
random.shuffle(gpt3_api_keys)
random.shuffle(gpt4_api_keys)
def cycle_keys(openai_api_keys):
    while True:
        for key in openai_api_keys:
            yield key
gpt3_key_generator = cycle_keys(gpt3_api_keys)
gpt4_key_generator = cycle_keys(gpt4_api_keys)

def key_generator(model_name):
    if model_name in ["gpt-3.5-turbo", "gpt-3.5-turbo-0301", "gpt-3.5-turbo-0613", "text-davinci-003", "text-davinci-002", "curie", "text-curie-001", "text-babbage-001", "text-ada-001"]:
        return gpt3_key_generator
    elif model_name in ["gpt-4", "gpt-4-0314", "gpt-4-0613"]:
        return gpt4_key_generator


class Agent:
    def __init__(self, model_name: str, temperature: float, sleep_time: float = 0) -> None:
        """Create an agent (gpt series by default)

        Args:
            model_name(str): model name
            temperature (float): higher values make the output more random, while lower values make it more focused and deterministic
            sleep_time (float): sleep against rate limiting
        """
        self.model_name = model_name
        self.temperature = temperature
        self.sleep_time = sleep_time
        self.memory_lst = []
        self.memory_lst_idx = np.array([])

    @backoff.on_exception(backoff.expo, (RateLimitError, APIError, ServiceUnavailableError, APIConnectionError, AuthenticationError), max_tries=5)
    def query(self, messages: "list[dict]", max_tokens: int, api_key: str, temperature: float) -> str:
        """make a query

        Args:
            messages (list[dict]): chat history in turbo format
            max_tokens (int): max token in api call
            api_key (str): openai api key
            temperature (float): sampling temperature

        Raises:
            OutOfQuotaException: the apikey has out of quota
            AccessTerminatedException: the apikey has been ban

        Returns:
            str: the return msg
        """
        # assert self.model_name in support_models, f"Not support {self.model_name}. Choices: {support_models}"
        try:
            openai.api_base = self.api_base
            response = openai.ChatCompletion.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                api_key=api_key,
                presence_penalty=0.75
            )
            gen = response['choices'][0]['message']['content']
            return gen

        except RateLimitError as e:
            if "You exceeded your current quota, please check your plan and billing details" in e.user_message:
                self.openai_api_keys.remove(api_key)
                print(f'Out Of Quota: {api_key}')
                raise OutOfQuotaException(api_key)
            elif "Your access was terminated due to violation of our policies" in e.user_message:
                self.openai_api_keys.remove(api_key)
                print(f'Access Terminated: {api_key}')
                raise AccessTerminatedException(api_key)
            else:
                raise e

    def merge_memory_lst(self, memory_lst):
        merged_memory_lst = []
        role, content = None, ""
        for memory in memory_lst:
            if memory["role"] == role:
                content = content + "\n\n" + memory["content"]
                continue
            else:
                if role != None:
                    merged_memory_lst.append({"role": role, "content": content.strip()})
                role = memory["role"]
                content = memory["content"]
        merged_memory_lst.append({"role": role, "content": content.strip()})
        return merged_memory_lst
        
    def set_meta_prompt(self, meta_prompt: str, survive_round: int = 9999):
        """Set the meta_prompt

        Args:
            meta_prompt (str): the meta prompt
        """
        self.memory_lst.append({"role": "system", "content": f"{meta_prompt}"})
        self.memory_lst_idx = np.append(self.memory_lst_idx, survive_round)

    def add_event(self, event: str, survive_round: int = 9999):
        """Add an new event in the memory

        Args:
            event (str): string that describe the event.
        """
        self.memory_lst.append({"role": "user", "content": f"{event}"})
        self.memory_lst_idx = np.append(self.memory_lst_idx, survive_round)

    def add_memory(self, memory: str, survive_round: int = 9999):
        """Monologue in the memory

        Args:
            memory (str): string that generated by the model in the last round.
        """
        self.memory_lst.append({"role": "assistant", "content": f"{memory}"})
        self.memory_lst_idx = np.append(self.memory_lst_idx, survive_round)

    def ask(self, temperature: float=None):
        """Query for answer

        Args: temperature(float): If temperature is not specified, sample by self.temperature
        """
        time.sleep(self.sleep_time)

        memory_lst = copy.deepcopy(self.memory_lst)
        memory_lst = np.array(memory_lst)
        memory_lst = memory_lst[self.memory_lst_idx > 0]
        self.memory_lst_idx -= 1
        memory_lst = list(memory_lst)

        num_context_token = sum([num_tokens_from_string(m["content"], self.model_name) for m in memory_lst])
        max_tokens = model2max_context[self.model_name] - num_context_token
        
        # # merge multi user contents
        # memory_lst = self.merge_memory_lst(memory_lst)
        
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S").split(':')
        start_time = 60 * int(current_time[0]) + int(current_time[1])
        while True:
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S").split(':')
            end_time = 60 * int(current_time[0]) + int(current_time[1])
            step_time = end_time - start_time
            if step_time // 2 > 0 and step_time % 2 == 0:
                print(f'Out of Time: {step_time} mins')
            if step_time > 5:
                raise TimeOutException
            try:
                if cycle_all_keys:
                    return self.query(memory_lst, max_tokens, api_key=next(key_generator(self.model_name)), temperature=temperature if temperature else self.temperature)
                else:
                    return self.query(memory_lst, max_tokens, api_key=random.choice(self.openai_api_keys), temperature=temperature if temperature else self.temperature)
            except:
                time.sleep(5)

        # return self.query(memory_lst, max_tokens, api_key=next(key_generator), temperature=temperature if temperature else self.temperature)


class TurboPlayer(Agent):
    def __init__(self, model_name: str, name: str, secret_word: str, temperature:float, sleep_time: float) -> None:
        """Create a player in the spy game

        Args:
            model_name(str): model name
            name (str): name of this player
            secret_word (str): the secret word that this player holds
            temperature (float): higher values make the output more random, while lower values make it more focused and deterministic
            sleep_time (float): sleep against rate limiting
        """
        super().__init__(model_name, temperature, sleep_time)
        self.name = name
        self.secret_word = secret_word
        if cycle_all_keys:
            self.openai_api_keys = gpt4_api_keys if 'gpt-4' in self.model_name else gpt3_api_keys
            
        # if 'gpt-4' in model_name:
        #     self.api_base = "https://aigptx.top/v1"
        # else:
        #     self.api_base = "https://api.openai.com/v1"
        self.api_base = "https://api.openai.com/v1"


class DavinciPlayer(TurboPlayer):
    @backoff.on_exception(backoff.expo, (RateLimitError, APIError, ServiceUnavailableError, APIConnectionError, AuthenticationError), max_tries=5)
    def query(self, prompt: str, max_tokens: int, api_key: str, temperature: float) -> str:
        try:
            openai.api_base = self.api_base
            response = openai.Completion.create(
                model=self.model_name,
                prompt=prompt,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                presence_penalty=0.75
                )
            gen = response.choices[0].text.strip()
            gen = f"{self.name}: {gen}"
            return gen
    
        except RateLimitError as e:
            if "You exceeded your current quota, please check your plan and billing details" in e.user_message:
                self.openai_api_keys.remove(api_key)
                print(f'Out Of Quota: {api_key}')
                raise OutOfQuotaException(api_key)
            elif "Your access was terminated due to violation of our policies" in e.user_message:
                self.openai_api_keys.remove(api_key)
                print(f'Access Terminated: {api_key}')
                raise AccessTerminatedException(api_key)
            else:
                raise e


    def ask(self, temperature: float=None):
        time.sleep(self.sleep_time)
        
        memory_lst = copy.deepcopy(self.memory_lst)
        memory_lst = np.array(memory_lst)
        memory_lst = memory_lst[self.memory_lst_idx > 0]
        self.memory_lst_idx -= 1
        memory_lst = list(memory_lst)

        contents = [m["content"] for m in memory_lst]
        prompt = '\n\n'.join(contents) + f"\n\n{self.name}: "

        num_context_token = num_tokens_from_string(prompt, self.model_name)
        max_tokens = model2max_context[self.model_name] - num_context_token

        now = datetime.now()
        current_time = now.strftime("%H:%M:%S").split(':')
        start_time = 60 * int(current_time[0]) + int(current_time[1])
        while True:
            # print(self.openai_api_keys)
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S").split(':')
            end_time = 60 * int(current_time[0]) + int(current_time[1])
            step_time = end_time - start_time
            if step_time // 2 > 0 and step_time % 2 == 0:
                print(f'Out of Time: {step_time} mins')
            if step_time > 5:
                raise TimeOutException
            try:
                if cycle_all_keys:
                    return self.query(prompt, max_tokens, api_key=next(key_generator(self.model_name)), temperature=temperature if temperature else self.temperature)
                else:
                    return self.query(prompt, max_tokens, api_key=random.choice(self.openai_api_keys), temperature=temperature if temperature else self.temperature)
            except:
                time.sleep(5)


    def ask2(self, temperature: float=None):
        time.sleep(self.sleep_time)
        openai.api_base = self.api_base

        memory_lst = copy.deepcopy(self.memory_lst)
        memory_lst = np.array(memory_lst)
        memory_lst = memory_lst[self.memory_lst_idx > 0]
        self.memory_lst_idx -= 1
        memory_lst = list(memory_lst)

        try:
            contents = [m["content"] for m in memory_lst]
            prompt = '\n\n'.join(contents) + f"\n\n{self.name}: "

            num_context_token = num_tokens_from_string(prompt, self.model_name)
            max_tokens = model2max_context[self.model_name] - num_context_token
            api_key = random.choice(self.openai_api_keys)
            # api_key=next(key_generator)

            response = openai.Completion.create(
                model=self.model_name,
                prompt=prompt,
                api_key=api_key,
                temperature=temperature if temperature else self.temperature,
                max_tokens=max_tokens,
                presence_penalty=0.75
                )
            gen = response.choices[0].text.strip()
            gen = f"{self.name}: {gen}"
            return gen
    
        except RateLimitError as e:
            if "You exceeded your current quota, please check your plan and billing details" in e.user_message:
                raise OutOfQuotaException(api_key)
            elif "Your access was terminated due to violation of our policies" in e.user_message:
                raise AccessTerminatedException(api_key)
            else:
                raise e
            

class BardPlayer(TurboPlayer):
    def __init__(self, model_name: str, name: str, secret_word: str, temperature:float, sleep_time: float) -> None:

        super.__init__(model_name, name, secret_word, temperature, openai_api_keys, sleep_time)

        self.bard_token = random.choice(openai_api_keys)

        session = requests.Session()
        session.headers = {
                    "Host": "bard.google.com",
                    "X-Same-Domain": "1",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
                    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "Origin": "https://bard.google.com",
                    "Referer": "https://bard.google.com/",
                }
        
        session.cookies.set("__Secure-1PSID", self.bard_token)
        self.bard = Bard(token=self.bard_token, session=session, timeout=30)
        self.start_id = 0

    def ask(self, temperature: float=None):
        time.sleep(self.sleep_time)

        contents_all = [m["content"] for m in self.memory_lst]
        contents = contents_all[self.start_id: ]
        self.start_id = len(contents_all)
        content = '\n\n'.join(contents)
        bard_ans = self.bard.get_answer(content)['content']
        return bard_ans


class VicunaPlayer(Agent):
    def __init__(self, model_name: str, name: str, secret_word: str, temperature:float, sleep_time: float) -> None:

        support_models = ['vicuna', 'fastchat-t5', 'longchat']
        super().__init__(model_name, temperature, sleep_time)
        self.name = name
        self.secret_word = secret_word
        self.openai_api_keys = openai_api_keys

        assert self.model_name in support_models, f"Not support {self.model_name}. Choices: {support_models}"

        magic_path = os.path.abspath(__file__).rsplit('/', 1)[0]
        self.repetition_penalty = 1.0
        if model_name == "vicuna":
            model_path = f"{magic_path}/FastChat/vicuna-13b-v1.3"
        elif model_name == 'fastchat-t5':
            model_path = f"{magic_path}/FastChat/fastchat-t5-3b-v1.0"
            self.repetition_penalty = 1.2
        elif model_name == 'longchat':
            model_path = f"{magic_path}/FastChat/longchat-13b-16k"
        self.model, self.tokenizer = load_model(
            model_path,
            "cuda",
            1,
            1,
            False,
            False,
            revision="main",
            debug=False,
        )
        self.conv = get_conversation_template(model_path)

    def set_meta_prompt(self, meta_prompt: str):
        """Set the meta_prompt

        Args:
            meta_prompt (str): the meta prompt
        """
        self.memory_lst.append({"role": "system", "content": f"{meta_prompt}"})
        self.conv.append_message(self.conv.roles[0], str(meta_prompt))

    def add_event(self, event: str):
        """Add an new event in the memory

        Args:
            event (str): string that describe the event.
        """
        # if not self.memory_lst[-1]['role'] == 'user':
        self.memory_lst.append({"role": "user", "content": f"{event}"})
        self.conv.append_message(self.conv.roles[0], str(event))
        # else:
            # self.memory_lst[-1]['content'] += f"\n\n{event}"

    def add_memory(self, memory: str):
        """Monologue in the memory

        Args:
            memory (str): string that generated by the model in the last round.
        """
        self.memory_lst.append({"role": "assistant", "content": f"{memory}"})
        self.conv.replace_message(self.conv.roles[1], str(memory))

    def ask(self, temperature: float=None):
        time.sleep(self.sleep_time)
        
        self.conv.append_message(self.conv.roles[1], None)
        prompt = self.conv.get_prompt()
        input_ids = self.tokenizer([prompt]).input_ids
        input_ids = [input_ids[0]]

        output_ids = self.model.generate(
            torch.as_tensor(input_ids).cuda(),
            do_sample=True,
            temperature=temperature if temperature else self.temperature,
            repetition_penalty=self.repetition_penalty,
            max_new_tokens=200,
        )
        if self.model.config.is_encoder_decoder:
            output_ids = output_ids[0]
        else:
            output_ids = output_ids[0][len(input_ids[0]) :]
        outputs = self.tokenizer.decode(
            output_ids, skip_special_tokens=True, spaces_between_special_tokens=False
        )
        return outputs