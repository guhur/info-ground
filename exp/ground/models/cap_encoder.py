import copy
import torch
import torch.nn as nn
import numpy as np
import pytorch_transformers

import utils.io as io


def weights_init(m):
    if isinstance(m, nn.Linear):
        torch.nn.init.xavier_uniform(m.weight.data)
        m.bias.data.fill_(0.0)


class CapEncoderConstants(io.JsonSerializableClass):
    def __init__(self):
        super().__init__()
        self.model = 'BertModel'
        self.tokenizer = 'BertTokenizer'
        self.pretrained_weights = 'bert-base-uncased'
        self.max_len = 15
        self.output_attentions = False


class CapEncoder(nn.Module,io.WritableToFile):
    def __init__(self,const):
        super().__init__()
        self.const = copy.deepcopy(const)
        output_hidden_states = False
        if self.const.output_attentions is True:
            output_hidden_states = True
        self.model = getattr(
            pytorch_transformers,
            self.const.model).from_pretrained(
                self.const.pretrained_weights,
                output_hidden_states=output_hidden_states,
                output_attentions=self.const.output_attentions)
        self.tokenizer = getattr(
            pytorch_transformers,
            self.const.tokenizer).from_pretrained(self.const.pretrained_weights)
    
    def random_init(self):
        self.model.apply(weights_init)

    @property
    def pad_token(self):
        return self.tokenizer.pad_token

    @property
    def cls_token(self):
        return self.tokenizer.cls_token

    @property
    def sep_token(self):
        return self.tokenizer.sep_token

    @property
    def pad_token_id(self):
        return self.tokenizer._convert_token_to_id(self.pad_token)

    def tokenize(self,caption):
        token_ids = self.tokenizer.encode(caption,add_special_tokens=True)
        tokens = [
            self.tokenizer._convert_id_to_token(t_id) for t_id in token_ids]
        return token_ids, tokens

    def pad_list(self,list_to_pad,pad_item,max_len):
        L = len(list_to_pad)
        if L==max_len:
            padded_list = list_to_pad[:]
        elif L > max_len:
            padded_list = list_to_pad[:max_len]
        else:
            padding = []
            for i in range(max_len-L):
                padding.append(pad_item)
            
            padded_list = list_to_pad + padding
        
        return padded_list

    def tokenize_batch(self,captions,pad_tokens=True,max_len=None):
        batch_token_ids = []
        batch_tokens = []
        token_lens = []
        max_token_len = 0
        for cap in captions:
            token_ids, tokens = self.tokenize(cap)
            batch_token_ids.append(token_ids)
            batch_tokens.append(tokens)
            token_len = len(tokens)
            token_lens.append(token_len)
            max_token_len = max(max_token_len,token_len)

        if max_len is not None:
            max_token_len = min(max_len,max_token_len)

        if pad_tokens is True:
            for i in range(len(captions)):
                batch_token_ids[i] = self.pad_list(
                    batch_token_ids[i],
                    self.pad_token_id,
                    max_token_len)
                batch_tokens[i] = self.pad_list(
                    batch_tokens[i],
                    self.pad_token,
                    max_token_len)
        
        return batch_token_ids, batch_tokens, token_lens

    def get_token_mask(self,batch_tokens):
        B = len(batch_tokens)
        T = len(batch_tokens[0])
        mask = np.zeros([B,T],dtype=np.float32)
        for b in range(B):
            tokens = batch_tokens[b]
            for t in range(T):
                if tokens[t] in [self.pad_token,self.sep_token,self.cls_token]:
                    mask[b,t] = 1
        
        return mask
    
    
    def select_embed(self,embed,token_ids):
        max_tokens = token_ids.size(1)
        B,T,D = embed.size()
        token_embed = torch.zeros([B,max_tokens,D],dtype=torch.float32).cuda()
        mask = torch.zeros([B,max_tokens],dtype=torch.float32).cuda()
        for b in range(B):
            for j in range(max_tokens):
                token_id = token_ids[b,j]
                if token_id == -1 or token_id >= T:
                    mask[b,j] = 1
                    continue
                
                token_embed[b,j] = embed[b,token_id]
        
        return token_embed, mask


    def forward(self,batch_token_ids):
        output = self.model(batch_token_ids)
        if self.const.output_attentions is True:
            embed = output[0]
            att = output[-1]
            return embed, att
        else:
            embed = output[0]
            return embed


if __name__=='__main__':
    const = CapEncoderConstants()
    const.output_attentions = True
    cap_encoder = CapEncoder(const)
    caps = ['i am here for fun','what are you here for?','A couple captain married .']
    token_ids, tokens, token_lens = cap_encoder.tokenize_batch(caps)
    token_ids = torch.LongTensor(token_ids)
    output = cap_encoder(token_ids)
    import pdb; pdb.set_trace()
