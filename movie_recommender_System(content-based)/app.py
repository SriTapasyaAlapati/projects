import streamlit as st
import pickle
d=pickle.load(open('movie_dict.pkl','rb'))
s=pickle.load(open('similarity.pkl','rb'))
st.title("Movie Recommender")
def recommendmovie(movie):
    movie=movie.lower()
    index = d[d['title'].str.lower() == movie]
    if(index.empty):
        return ["no movie found with this name"]
    a=index.index[0]
    distances=s[a]
    movielist=sorted(list(enumerate(distances)),reverse=True,key=lambda x:x[1])[1:6]
    a=[]
    for i in movielist:
         a.append((d.iloc[i[0]]['title']))
    return a
movie=st.selectbox("Select your movie",d['title'].values)
if(st.button('Recommend')):
    rec=recommendmovie(movie)
    for i in rec:
        st.write(i)
