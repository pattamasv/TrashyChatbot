from fastai.vision import *
from flask import Flask, request, abort, render_template
from sqlalchemy import desc
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import *
from linebot.models.responses import Content
from linebot.models.messages import*
from linebot.models.template import *
from PIL import Image, ImageFile
from geopy.distance import *
import io
import json,requests
import geopy.distance as ps
import pandas as pd
import numpy as np
from models import db,users
from config import Config
from datetime import datetime, timezone, timedelta

path = './'
learn = load_learner(path, 'export.pkl')
#print('model loaded!')

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

db.init_app(app)
#db = SQLAlchemy(app)

@app.before_first_request
def create_table():
    db.create_all()

ImageFile.LOAD_TRUNCATED_IMAGES = True

channelAccessToken = "uO5sdEUKGjHFVUppEXqj4ptfNSr1FoAublAG4Keu6AuDc40kDxF9gYnBKCCRPemc6hqYATEdhZ/vtQIdBF8bQYcmXgD7ennBH0HWK2hh5vExmsF5y09GWAddEAkobS+xmaoxsj/vzBTYTPyHjfkKwAdB04t89/1O/w1cDnyilFU="
channelSecret = "bf23c31dc5d926e28c188d0c3018078e"

CONFIDENCE_THRESHOLD = 70
PIXEL_RESIZE_TO_h = 384
PIXEL_RESIZE_TO_w = 384

line_bot_api = LineBotApi(channelAccessToken)
handler = WebhookHandler(channelSecret)

wongpanit = pd.read_excel('wongpanit.xlsx')
refunex = pd.read_excel('Refun Machine Location.xlsx')
price = pd.read_excel('predicted_result.xlsx')
price.rename(columns={'Unnamed: 4':'โลหะ','Unnamed: 1':'กระดาษ','Unnamed: 2':'แก้ว','Unnamed: 3':'พลาสติก'},inplace=True)

qr = QuickReply(items=[QuickReplyButton(action=MessageAction(label="วิธีใช้", text="ขั้นตอนการใช้งาน")),
                    QuickReplyButton(action=MessageAction(label="พิกัดใกล้ฉัน", text="พิกัดใกล้ฉัน")),
                    QuickReplyButton( action=CameraAction(label="ถ่ายรูปขยะ")),
                    QuickReplyButton( action=CameraRollAction(label="เลือกรูปขยะ")),
                    QuickReplyButton(action=LocationAction(label="ส่งตำแหน่ง")),
                    QuickReplyButton(action=MessageAction(label="Dashboard", text="Dashboard")),
                    QuickReplyButton(action=MessageAction(label="Statistic", text="Statistic")) ])

@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    print("# Webhook event:\n", body)
    print('-'*100)

    app.logger.info("Request body: " + body)

    try:
         handler.handle(body ,signature)
    except InvalidSignatureError:
         abort(400)
    
    return 'OK'

@app.route('/')
def main():   
    return render_template('index.html', users = users.query.order_by(desc(users.timestamp)).all())

@app.route('/stat')
def statistic():
    user = len(users.query.all())
    paper = len(users.query.filter_by(trash = 'paper').all())
    glass = len(users.query.filter_by(trash = 'glass').all())
    metal = len(users.query.filter_by(trash = 'metal').all())
    plastic = len(users.query.filter_by(trash = 'plastic').all())
    trash = len(users.query.filter_by(trash = 'trash').all())
    waste = len(users.query.filter_by(trash = 'biological').all())
    dangerous = len(users.query.filter_by(trash = 'dangerous').all())
    
    return render_template('statistic.html', paper=paper, glass=glass, metal=metal, plastic=plastic, trash=trash, waste=waste, dangerous=dangerous)

@handler.add(PostbackEvent)
def handle_post(event:PostbackEvent)-> None : # echo function 
      data  = event.postback.data
      data1 = eval(data)
    
      lat = data1[0]['latitude']
      lng = data1[0]['longitude']
      if  data1[1]['trashtype']=='plastic':
          ptype = 'ตู้รีฟัน'
          reply_message = handle_location(lat,lng,refunex,1)
      else:
          ptype = 'วงษ์พาณิชย์'
          reply_message = handle_location(lat,lng,wongpanit,1)
     
      line_bot_api.reply_message(event.reply_token, [TextSendMessage(text = reply_message)])

      return reply_message

@handler.add(MessageEvent, message=(LocationMessage,ImageMessage,TextMessage))
def handle_message(event: MessageEvent)-> None : # echo function
        #Text
        greeting = ['สวัสดีค่ะ','สวัสดีครับ','สวัสดี']
        howtouse = ['Trashy Chatbot ทำอะไรได้บ้าง','ทำอะไรได้บ้าง','ทำไรได้บ้าง','ใช้ยังไง','ต้องทำยังไง','ขั้นตอนการใช้งาน','วิธีใช้','ขอวิธีใช้หน่อย','วิธีใช้งาน','ต้องทำอะไรบ้าง']
        end = ['ขอบคุณ','ขอบคุณค่ะ','ขอบคุณครับ','เอาไว้ก่อน','ยังไม่ต้องการขาย']
        yes = ['ต้องการขาย','พิกัดใกล้ฉัน','ต้องการสะสมแต้มหรือขาย']
        web = ['Dashboard', 'Statistic']
      
        if isinstance(event.message, TextMessage):
            for g in greeting:
                if (g == event.message.text ):
                    reply_message = 'สวัสดีค่ะ'
                    line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply_message, quick_reply=qr)])        
                    break

            for h in howtouse:
                if (h == event.message.text ):
                    t1 = '1.ถ่ายรูปขยะที่ต้องการทิ้ง ส่งไปยังแทรชชี่แชทบอท (โดยพยายามถ่ายให้พื้นหลังรูปขยะเป็นสีขาว) เพื่อให้แทรชชี่แนะนำการจัดการกับขยะประเภทนั้นๆ'
                    t2 = '2.ส่งตำแหน่งที่ตั้งปัจจุบันของผู้ใช้ไปยังแทรชชี่แชทบอท เพื่อให้แทรชชี่แนะนำสถานที่รับซื้อขยะรีไซเคิลที่อยู่ใกล้กับผู้ใช้'
                    reply_message = t1+'\n'+t2
                    line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply_message, quick_reply=qr)])      
                    break

            for y in yes:
                if (y == event.message.text ):
                    #reply_message = 'หากต้องการขายสามารถส่งโลเคชั่นมาที่แชทเพื่อให้เราแนะนำวงษ์พาณิชย์สาขาที่ใกล้กับคุณ'
                    reply_message = 'โปรดส่งโลเคชันของคุณมาที่แชทเพื่อให้เราแนะนำพิกัดที่ใกล้กับคุณ'
                    line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply_message, quick_reply=qr)])    
                    break

            for e in end:
                if (e == event.message.text ):
                    reply_message = 'Trashy Chatbot ยินดีให้บริการค่ะ ขอบคุณค่ะ'
                    line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply_message)])
                    break
            
            for w in web:
                if (event.message.text == 'Dashboard' ):
                    reply_message = 'https://trashychatbot.herokuapp.com/'
                    line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply_message, quick_reply=qr)])       
                    break

                elif (event.message.text == 'Statistic' ):
                    reply_message = 'https://trashychatbot.herokuapp.com/stat'
                    line_bot_api.reply_message(event.reply_token, [TextSendMessage(text=reply_message, quick_reply=qr)])        
                    break

        #Image
        if isinstance(event.message, ImageMessage):
            image = download_and_resize_image(event,PIXEL_RESIZE_TO_w, PIXEL_RESIZE_TO_h)
            data = open_image(image)
            #data = data.resize((3,384,512))
            #data = PILImage(PILImage.create(TEST_IMAGE).resize((600,400)))
            print(data)
           
            predicted_class, predicted_index, outputs = learn.predict(data)
            
            res = str(predicted_class)
            print(res)
            #print(str(outputs))

            if res == 'glass':
                trashtype = 'แก้ว'
                prob = float('%.2f' %(outputs[2]*100))
            elif res == 'paper':
                trashtype = 'กระดาษ'
                prob = float('%.2f' %(outputs[4]*100))
            elif res == 'metal':
                trashtype = 'โลหะ'
                prob = float('%.2f' %(outputs[3]*100))
            elif res == 'plastic':
                trashtype = 'พลาสติก'
                prob = float('%.2f' %(outputs[5]*100))
            elif res == 'trash':
                trashtype = 'ขยะทั่วไป'
                prob = float('%.2f' %(outputs[6]*100))
            elif res == 'biological':
                trashtype = 'ขยะเปียก'
                prob = float('%.2f' %(outputs[0]*100))
            elif res == 'dangerous':
                trashtype = 'ขยะอันตราย'
                prob = float('%.2f' %(outputs[1]*100))
            else:
                #trashtype = 'อื่นๆ'
                pass
            
            profile = line_bot_api.get_profile(event.source.user_id)
                    
            tz = timezone(timedelta(hours = 7))

            # Create a date object with given timezone
            date = datetime.now(tz=tz)
            time_string = date.strftime("%d/%m/%Y, %X")

            userid = profile.user_id
            displayname = profile.display_name
            pictureurl = profile.picture_url
            timestamp = time_string

            u = users(userid=userid, displayname=displayname, pictureurl=pictureurl, trash=res, timestamp=timestamp)

            if trashtype == 'แก้ว' or trashtype =='กระดาษ' or trashtype =='โลหะ' or trashtype =='พลาสติก':
                bin = 'ถังขยะสีเหลือง'
                reply_type = 'ประเภทขยะของคุณคือ %s ควรทิ้งใน%s'%(trashtype,bin)
                reply_plastic = 'หรือคุณสามารถนำไปสะสมแต้มได้ที่ตู้รีฟันเพื่อแลกของรางวัล หรือนำไปขายได้ที่วงษ์พาณิชย์'
                reply_notplastic = 'หรือคุณสามารถนำไปขายได้ที่วงษ์พาณิชย์'
                url = 'https://www.img.in.th/images/6d4320aa5180bb8960d0d520a58d25b7.jpg'
                app.logger.info("url=" + url)
                predictprice = getprice(price,trashtype)
                
                if trashtype == 'พลาสติก':
                    confirm_template = ConfirmTemplate(text=predictprice+' ' +'ต้องการสะสมแต้มหรือขายไหม?', 
                        actions=[
                            MessageAction(label='ใช่', text='ต้องการสะสมแต้มหรือขาย'),
                            MessageAction(label='ไม่', text='เอาไว้ก่อน')
                        ])

                    reply_message = [TextSendMessage(text=reply_type), ImageSendMessage(url, url), TextSendMessage(text=reply_plastic) ,TemplateSendMessage(alt_text='Confirm alt text', template=confirm_template,quick_reply = qr)]
                    line_bot_api.reply_message(event.reply_token, reply_message) 
                    
                    db.session.add(u)
                    db.session.commit()

                else: 
                    confirm_template = ConfirmTemplate(text=predictprice+' ' +'ต้องการขายไหม?', 
                        actions=[
                            MessageAction(label='ใช่', text='ต้องการขาย'),
                            MessageAction(label='ไม่', text='เอาไว้ก่อน'),
                        ])
                    
                    reply_message = [TextSendMessage(text=reply_type), ImageSendMessage(url, url), TextSendMessage(text=reply_notplastic) ,TemplateSendMessage(alt_text='Confirm alt text', template=confirm_template,quick_reply = qr)]
                    line_bot_api.reply_message(event.reply_token, reply_message) 
                
                    db.session.add(u)
                    db.session.commit()

            elif trashtype == 'ขยะทั่วไป':
                bin = 'ถังขยะสีน้ำเงิน'
                url = 'https://www.img.in.th/images/d0edc27448de8591252bfeee4392ccd2.jpg'
                app.logger.info("url=" + url)
                reply_type = 'ประเภทขยะของคุณคือ %s ควรทิ้งใน%s'%(trashtype,bin)

                reply_message = [TextSendMessage(text=reply_type), ImageSendMessage(url, url, quick_reply = qr)]
                line_bot_api.reply_message(event.reply_token, reply_message) 
                
                db.session.add(u)
                db.session.commit()

            elif trashtype == 'ขยะอันตราย':
                bin = 'ถังขยะสีแดง'
                url = 'https://www.img.in.th/images/4fe2a116e8323985bd4a86ace49ddd07.jpg'
                app.logger.info("url=" + url)
                reply_type = 'ประเภทขยะของคุณคือ %s ควรทิ้งใน%s'%(trashtype,bin)

                reply_message = [TextSendMessage(text=reply_type), ImageSendMessage(url, url, quick_reply = qr)]
                line_bot_api.reply_message(event.reply_token, reply_message) 
                
                db.session.add(u)
                db.session.commit()

            elif trashtype == 'ขยะเปียก':
                bin = 'ถังขยะสีเขียว'
                url = 'https://www.img.in.th/images/bc79d41e1beeab5cdb0c88f0f6a24678.jpg'
                app.logger.info("url=" + url)
                reply_type = 'ประเภทขยะของคุณคือ %s ควรทิ้งใน%s'%(trashtype,bin)

                reply_message = [TextSendMessage(text=reply_type), ImageSendMessage(url, url, quick_reply = qr)]
                line_bot_api.reply_message(event.reply_token, reply_message) 
                
                db.session.add(u)
                db.session.commit()

            else:
                pass

        #Location
        if isinstance(event.message, LocationMessage):
            lat = event.message.latitude
            lng = event.message.longitude
            plastic = {"trashtype":'plastic'}
            notplastic = {"trashtype":'notplastic'}
            prog_dict = {"latitude": lat,"longitude": lng}
            prog_string = json.dumps(prog_dict)
            prog_string1 = json.dumps(plastic)
            prog_string2 = json.dumps(notplastic)
            
            confirm_template = ConfirmTemplate(text='ต้องการพิกัดวงษ์พาณิชย์หรือตู้รีฟัน?', 
                actions=[
                         PostbackAction(
                            label='วงษ์พาณิชย์',
                            text='วงษ์พาณิชย์',
                            data=(prog_string+','+prog_string2)
                        ),
                        #MessageAction(label='ตู้รีฟัน', text='ตู้รีฟัน'),
                        PostbackAction(
                            label='ตู้รีฟัน',
                            display_text='ตู้รีฟัน',
                            data=(prog_string+','+prog_string1)
                        ),
                    ])
            
            reply_message = [TemplateSendMessage(alt_text='Confirm alt text', template=confirm_template, quick_reply = qr)]
            line_bot_api.reply_message(event.reply_token, reply_message) 

#DownloadImage
def download_and_resize_image(event: MessageEvent, PIXEL_RESIZE_TO_w, PIXEL_RESIZE_TO_h) -> bytes:
    src_image = io.BytesIO()
    message_content: Content = line_bot_api.get_message_content(event.message.id)

    for chunk in message_content.iter_content():
        src_image.write(chunk)

    with Image.open(src_image) as img:
        width, height = img.size
        if width < PIXEL_RESIZE_TO_w and height < PIXEL_RESIZE_TO_h:
           return src_image.getvalue()

        dst_image = io.BytesIO()
        img.thumbnail((PIXEL_RESIZE_TO_w, PIXEL_RESIZE_TO_h))
        img.save(dst_image, format=img.format)

    return dst_image

#ResponseLocationFromExcel
def handle_location(lat,lng,cdat,topK):
    result = getdistance(lat, lng,cdat)
    result = result.sort_values(by='km')
    result = result.iloc[0:topK]
    txtResult = ''
    for i in range(len(result)):
        nameshop = str(result.iloc[i]['Name'])
        kmdistance = '%.1f'%(result.iloc[i]['km'])
        newssource = str(result.iloc[i]['News_Source'])
        txtResult = txtResult + '%s อยู่ห่างจากคุณ %s กิโลเมตร\n%s\n\n'%(nameshop,kmdistance,newssource)
    return txtResult[0:-2]

def getdistance(latitude, longitude,cdat):
    coords_1 = (float(latitude), float(longitude))
    ## create list of all reference locations from a pandas DataFrame
    latlngList = cdat[['Latitude','Longitude']].values
    ## loop and calculate distance in KM using geopy.distance library and append to distance list
    kmsumList = []
    for latlng in latlngList:
      coords_2 = (float(latlng[0]),float(latlng[1]))
      kmsumList.append(ps.geodesic(coords_1, coords_2).km)
    cdat['km'] = kmsumList
    return cdat

def getprice(price,trashtype):
    result = pricecal(price,trashtype)
    if result > 0:
      reply = 'ขณะนี้ราคากำลังขึ้น'
    elif result < 0:
      reply = 'ขณะนี้ราคากำลังลง'
    elif result == 0:
      reply = 'ขณะนี้ราคากำลังนิ่ง'
    else:
      pass
    return reply 

def pricecal(price,trashtype):
    data = price['%s'%trashtype].values
    price = (data[0]-data[6])/data[6]
    return price
  
if __name__ == '__main__':
    app.run()